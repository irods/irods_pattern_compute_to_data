# irods_pattern_compute_to_data

---

Setup for Compute to Data Training / Demonstration
-------------------------------------------------------------------------------------------------------

   * Follow "Administration - Getting Started" from UGM 2019 to fullfill prerequisites:

      - set up iRODS 4.2.7 via package install
      - install Docker-CE
      - skip the audit plugin setup if desired

Clone this repo:
```
git clone https://github.com/irods/irods_pattern_compute_to_data
```

Add development packages:

```
  sudo apt-get -y install \
   irods-externals-cmake3.5.2-0 \
   irods-externals-clang3.8-0 \
   irods-externals-qpid-with-proton0.34-0 \
   irods-dev
```

In Bash, as ubuntu user:

```
export PATH=/opt/irods-externals/cmake3.5.2-0/bin:$PATH
```

Build packages for
   - *compute to data* and
   - *register as admin* msvc:

```
cd
mkdir build_compute_to_data
cd build_compute_to_data
cmake ../irods_training/advanced/hpc_compute_to_data
make package
sudo dpkg -i irods-hpc-compute-to-data-example_*.deb

cd
mkdir build_register_microservice
cd build_register_microservice
cmake ../irods_training/advanced/hpc_compute_to_data/msvc__msiregister_as_admin/
make package
sudo dpkg -i irods-microservice-register_as_admin-*.deb
```

Cut and Paste setup :
---

```
# -- as user ubuntu :

cd /home/ubuntu/irods_training/advanced/hpc_compute_to_data/jupyter_notebook
docker build -t testimages/jupyter-digital-filter .
sudo apt-get -y install irods-rule-engine-plugin-python
sudo apt-get -y install python-pip
sudo usermod -aG docker irods
pip install docker --user

# -- as user irods :

# Create /etc/irods/core.py with the following  import:

# (Follow Native REP stanza with Python REP configuration stanza)

    {
      "instance_name": "irods_rule_engine_plugin-python-instance",
      "plugin_name": "irods_rule_engine_plugin-python",
      "plugin_specific_configuration": {}
    }


iadmin mkuser alice rodsuser
iadmin moduser alice password apass

#=== ubuntu

    iinit ubuntu user as alice/apass

#===
 
add to /etc/irods/core.py

from compute_to_data import *

sudo su irods -c '~/irodsctl restart'

```

Also (after installing the compute-to-data and microservice-register_as_admin packages):


  1. There's a different docker image to build for this version --

     ```
     ubuntu $ cd ~/jupyter_container
     ubuntu $ docker build -t jupyter_sobel:latest -f Dockerfile.jupyter_sobel .
     ```

  2. add the line 'from compute_container import *' to /etc/irods/core.py. (This is all that is needed
     in terms of Python rule engine code.)

  3. Instead of the storage resources/AVUs in the UGM2019 presentation, we create the following
     setup for the data to be routed "compute-side" :
     ```
     irods $  mkdir /var/lib/irods/compute_Vault
     irods $  iadmin mkresc compute_resc unixfilesystem `hostname`:/var/lib/irods/compute_Vault
     irods $  imeta set -R compute_resc irods::resc_compute_role image_processing
     ```

  4. Create the .json data objects describing C2D applications settings --
     ```
     irods $  imkdir  /tempZone/home/configured_applications
     irods $  ichmod read public /tempZone/home/configured_applications
     irods $  ichmod inherit /tempZone/home/configured_applications
     irods $  icd /tempZone/home/configured_applications ; cd ; for x in sobel*.json; do iput -f $x . ;done
     irods $  imeta set -d sobel_execute.json   irods::compute::application  sobel_auto_run  docker
     irods $  imeta set -d sobel_notebook.json  irods::compute::application  sobel_jupyter_nb  docker
     ```

  5. set the native rulebases in the server_config to:
     ```
                    "re_rulebase_set": [
                        "compute_to_data_routing",
                        "container_calls",
                        "core"
                    ],
     ```


Running the Compute To Data Demonstration
---

```

	ubuntu $ cd ; python generate_csv_input.py >square.img.csv
	ubuntu $ icd; imkdir input_data
	ubuntu $ iput square.img.csv  input_data
```
To show that data object "square.img.csv" has landed in the correct storage resource:
```
	ubuntu $ ils -l input_data
        /tempZone/home/alice/input_data:
          alice             0 compute_resc         2080 2020-01-15.16:00 & square.img.csv
```

To launch the "sobel_execute.json" container synchronously:
```
	ubuntu $ irule -F launch_container_for_input.r \
                   '*outcoll="/tempZone/home/alice/output_synchronous"' \
                   '*app="*/sobel_execute.json"'
```

To show the resulting data object "edge_detected_square.img.csv" was registered,
```
	ubuntu $ ils /tempZone/home/alice/output_synchronous
        /tempZone/home/alice/output_synchronous:
          edge_detected_square.img.csv
          sobel_out.ipynb
```

To launch the "sobel_notebook.json" container interactively:
```
	ubuntu $ irule -F launch_container_for_input.r \
                   '*outcoll="/tempZone/home/alice/output_interactive"' \
                   '*app="*/sobel_notebook.json"'
```
   - After a few seconds, the URL of the interactive Jupyter notebook will appear.
     e.g. http://0.0.0.0:8888/?token=c9e736ae61059798bd37e05cef03f6b2c3fe8d6ae0bb055c
     ("0.0.0.0" can be replaced with the docker host machine's hostname or IP)


Open the URL in a local browser to display the Jupyter Notebook main page.


Show the iRODS delay queue watching for the interactive container to exit:
        ```
        ubuntu $ iqstat
        id     name
        10097  irods_policy_poll_application(*host, *context, *id, *attr_out, *status_out, "600")
        ```


Highlight the first Jupyter notebook cell and hit <shift-Return> to execute each cell in succession.


Show the interactive results are not yet registered in iRODS:

        ```
	ubuntu $ ils /tempZone/home/alice/output_interactive
        remote addresses: 127.0.1.1 ERROR: lsUtil: srcPath /tempZone/home/alice/output_interactive does not exist or user lacks access permission
        ```


Select the Quit button in the upper right corner of the Jupyter notebook main page.
This will exit the notebook and the container will exit.


Show the interactive results are now registered in iRODS:

        ```
        ubuntu $ ils /tempZone/home/alice/output_interactive
        /tempZone/home/alice/output_interactive:
          edge_detected_square.img.csv
        ```


#===========================================================================================

If a VM security (or something else that is running) conflicts with the default http port (8888)
used to display the  notebook, choose a new port number and then:

    * change all occurrences of the old port "8888" in the sobel_notebook.json app configuration file
      and iput -f the modified file into the collection '/tempZone/home/configured_applications'

#------------------

Notes --

If by trial and repetition more than one docker app is using the same notebook display port (or the same output
collection) as a new app instance about to be spawned, you can do the following to get rid of the old one(s):

```
 $ docker rm -f $(docker ps -aql)
```

(using  "-aql" deletes the last docker app run, using "-aq" would terminate all running docker applications).

Probably need to another policy endpoint as a counterpart for for "docker <containerId> stop" but this
isn't quite complete yet.

