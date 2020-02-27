from os.path import dirname,basename
import os
from os.path import isdir
import re
import socket
import warnings
import json
from genquery import row_iterator, AS_DICT, AS_LIST
import time
import tempfile

#---------------------- support routines, objects ----------------------------

docker_error_NotFound = None

try:
  import reprlib as _repr
except:
  import repr as _repr
class irods_repr(_repr.Repr):
  def repr_str(self,s,level): return "'{}'".format(s)
  def repr_list(self,s,level):
    x = self.repr(tuple(s)).rstrip()
    return x[:-2]+")" if x.endswith(",)") else x

from bytes_unicode_mapper import *
to_bytestring = lambda struc : map_strings_recursively( struc , to_bytes('utf-8'))
coll_name_regex = re.compile(r'^/(?P<zone>.*?)/(?P<v_relative_path>((?P<v_parent>.+?)/)?(?P<v_child>[^/]+))$')
#Example logical path decomposition:
#   /tempZone/home/alice/collection/subcollection_or_object
#   [--zone--]
#   [-------parent_with_zone-------]
#            [--------------v_relative_path----------------]
#            [------v_parent-------]
#                                  [-------v_child---------]
def _parse_collection_name( name ):
    d = coll_name_regex.match( name ).groupdict()
    d['parent_with_zone'] = '/{zone}/{v_parent}'.format(**d)
    return d

#-------------------------- main calls/rules  --------------------------------

def _resc_vault_path(callback, resc_name):
    results = [r for r in 
               row_iterator('RESC_VAULT_PATH',"RESC_NAME = '{}'".format(resc_name),AS_DICT,callback)]
    return results[0]['RESC_VAULT_PATH'] if results else ''


def _ensure_vault_path (callback, coll_name, resc_name, create = False):
    phys_path = ''
    ext_v_path = _resc_vault_path (callback , resc_name)
    if ext_v_path:
        fields = _parse_collection_name (coll_name)
        phys_path = "/".join((ext_v_path, fields['v_relative_path']))
        if create and not os.path.isdir(phys_path):
            try: os.makedirs( phys_path )
            except: pass
    return (phys_path if os.path.isdir(phys_path) 
            else "")


def _list_all_application_configs(callback, ctx, save_rows = None, as_lookup=False):
#   TODO :  renaming to irods::compute_to_data
    rows = scratch = [] 
    if isinstance(save_rows,list):    rows = save_rows
    elif isinstance(save_rows,tuple): rows = list(save_rows)
    if (rows is scratch) or (rows is save_rows):
        rows[:] = [ r for r in row_iterator( 
            "COLL_NAME,DATA_NAME,META_DATA_ATTR_VALUE",
            ("DATA_NAME like '%.json' "
            "and COLL_NAME like '%/configured_applications' "
            "and COLL_NAME not like '%/trash/%' "
            "and META_DATA_ATTR_NAME = 'irods::compute::application' "
            "and META_DATA_ATTR_VALUE like '_%' "
        #   "and META_DATA_ATTR_UNITS like 'docker' "
            ).format(**ctx) , AS_DICT, callback) ]
    return [ "{COLL_NAME}/{DATA_NAME}".format(**row) for row in rows ] if not as_lookup else \
           { row["META_DATA_ATTR_VALUE"]:"{COLL_NAME}/{DATA_NAME}".format(**row) for row in rows }


def _get_object_size(callback, path):
    rv = callback.msiObjStat( path , 0)
    size = 0
    if  rv['status' ] and rv['code'] == 0:
        size = int(rv['arguments'][1].objSize)
    return str(size)

def _read_data_object(callback, name):
    rv = callback.msiDataObjOpen (  "objPath={0}".format(name), 0 )
    returnbuffer = None
    desc = None
    if rv['status'] and rv['code'] >= 0:
        desc = rv['arguments'][1]
    if type(desc) is int:
        size = _get_object_size (callback,name)
        rv = callback.msiDataObjRead ( desc, size, 0 )
        returnbuffer = rv ['arguments'][2]
    return str(returnbuffer.buf)[:int(size)] if returnbuffer else ""

################# DOCKER applications API ################# 

#
# LIST ( context, list_out ) : enumerate available applications

def irods_container_Impl__list_applications ( args, cbk, rei ):
    ctx = to_bytestring (json.loads( args[0] ))
    config_results = []
    args[1] = irods_repr().repr(_list_all_application_configs(cbk, ctx, config_results))
    ctx ['app_configs'] =  _list_all_application_configs(cbk, ctx, tuple(config_results), as_lookup=True)
    args[0] = json.dumps(ctx,indent=4)

def _override_environment ( dst, new_env ):
    dstenv = dst["selected_app"].get("environment",{})
    for k,v in dst.items():
        if k.startswith ("Env__"): dstenv[k[5:]] = v
    dstenv.update( new_env )
    dst["selected_app"]["environment"] = dstenv
            
# 
# RUN ( context, input_colln, output_colln, extra_env, app_name, id_out, err_out )
#

def irods_container_Impl__run_application(args,callback,rei):

    ctx = to_bytestring (json.loads( args[0] ))
    (input_c, output_c, extra_env_vars, app) = args[1:5]
    if not app.startswith("/"):
        app = ctx['app_configs'].get(app)
    if app is not None:
        ctx['selected_app'] = {} if not app \
         else to_bytestring (json.loads( _read_data_object(callback, app)))
    _override_environment (ctx, to_bytestring( json.loads(extra_env_vars)))
    args[5:7] = ["", ""]  # argument offsets 5,6 => container_id , errmsg
    cli = _docker_client()
    if cli:
        host_v_outpath = ''
        in_out_mounts = []
        input_coll =  input_c or ctx['input_collection_hint']
        if input_coll:
            host_v_inpath = _ensure_vault_path (callback, input_coll, ctx['compute_resource'], create = False)
            in_out_mounts += ["{0}:{guest_working_dir}/{guest_input_subdir}:ro".format(host_v_inpath,**ctx["selected_app"])]
        output_coll = output_c
        if output_coll:
            host_v_outpath = _ensure_vault_path (callback, output_coll, ctx['compute_resource'], create = True)
            in_out_mounts += ["{0}:{guest_working_dir}/{guest_output_subdir}:rw".format(host_v_outpath,**ctx["selected_app"])]
        run_command = ctx["selected_app"].get("run_command")
        instance = cli.containers.run( ctx['selected_app']['image'], command = run_command,
                                       ports = ctx['selected_app'].get('ports'),
                                       environment = ctx['selected_app']['environment'], 
                                       detach = ctx['selected_app'].get('detach', True),
                                       volumes = in_out_mounts, tty = True, remove = True)
        if hasattr(instance,'id'):
            args[5] = to_bytestring ( instance.id )     # asynchronous case - register outputs when poll finds container exited
            if output_coll and host_v_outpath:
                ctx["selected_app"]["output_to_register"] = { host_v_outpath : output_coll }
        else:
            args[5] = ""                                # synchronous case - register outputs immediately
            args[6] = "container ID not returned when detach = True"
            if output_coll and host_v_outpath:
                callback.msiregister_as_admin ( output_coll, ctx['compute_resource'], host_v_outpath, "collection", 0)
        args[0] = json.dumps(ctx,indent=4) ## - give JSON-formatted context back to client
    else:
        args[6] = "Could not launch container"
 
#==================================================

#
#  EXEC (context, container_id, command, exitcode_out, stdout_out )
#

def irods_container_Impl__exec_command_in_application(args,callback,rei):
    ctx = to_bytestring (json.loads( args[0] ))
    (container_id, command) = args[1:3]
    cli = _docker_client()
    try:
        container = cli.containers.get(container_id)
    except docker_error_NotFound: container = None
    if container:
        result = container.exec_run ( command , stderr=False )
        args[3] = b'{}'.format(result.exit_code)
        args[4] = to_bytestring(result.output)
    else:
        args[3] = args[4] = ''

#   STOP (context, container_id) 
#        (poll for notebook server to be done and register output)
#

def irods_container_Impl__stop_application(args,callback,rei):
    ctx = to_bytestring (json.loads( args[0] ))
    (container_id, ) = args[1:2]
    cli = _docker_client()
    try:
        container = cli.containers.get(container_id)
    except docker_error_NotFound: container = None
    if container: 
        try: container.stop()
        except: pass


##  POLL (context, container_id, attributes_out, status_out, looping )
#   looping = '<intvalue>":       how many seconds to loop waiting for exit status if positive
#                       or indication to loop forever if negative
#           = '0' or '',  do not loop (check container status only once)

def irods_container_Impl__poll_application(args,callback,rei):
    ctx = to_bytestring (json.loads( args[0] ))
    (container_id, ) = args[1:2]
    if len(args) > 4 and args[4] != "":
        loop_seconds = int(args[4])
    else:
        loop_seconds = 0
    cli = _docker_client()
    logfile = tempfile.NamedTemporaryFile(mode="w+",prefix='c2d-poll-log-',delete=False,suffix='-'+container_id[:12])
    while True:
        try:
            container = cli.containers.get(container_id)
        except docker_error_NotFound:
            container = None
        if container is None:
            args[2] = ""
            args[3] = "exited?"
        else:
            args[2] = "{...}" # todo : subset of container.attrs (whole is larger than allotted AVU value field)
            args[3] = to_bytestring( container.status ) # 'created', 'running', exited'
        if args[3].startswith("exited"):
            delayed_register_info = ctx.get( "selected_app", {} ) and \
                                    ctx["selected_app"].get("output_to_register")
            if delayed_register_info:
                logfile.write("Registering output: {!r}\n".format(delayed_register_info))
                for physical,logical in delayed_register_info.items():
                    callback.msiregister_as_admin ( logical, ctx['compute_resource'], physical, "collection", 0)
            logfile.write("Exiting normally\n")
            break
        if loop_seconds != 0:
            logfile.write("Polling - at {} seconds...\n".format(loop_seconds))
            time.sleep(1)
            loop_seconds -= 1
        else:
            logfile.write("Exiting Poll operation due to timeout\n")
            break
        logfile.flush()
    if ctx: ctx["selected_app"]["status"] = args[3]
    args[0] = json.dumps(ctx,indent=4)

def _docker_client(get_info=None, re_raise=False):
    global docker_error_NotFound
    client = None
    with warnings.catch_warnings():      # - suppress warnings 
        warnings.simplefilter("ignore")  #   when loading ...
        import docker                    #     Python Docker API
        if docker_error_NotFound is None:
            docker_error_NotFound = docker.errors.NotFound
    try:
        client = docker.from_env()
        if isinstance(get_info,dict): get_info.update(client.info())
    except:
        client = None
        if re_raise: raise
    return client

