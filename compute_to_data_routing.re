
resc_from_compute_role ( *role )
{
    *resc = ""
    foreach (*r in select RESC_NAME, META_RESC_ATTR_VALUE where
                 META_RESC_ATTR_NAME = 'irods::resc_compute_role') 
    {
        *resc = *r.RESC_NAME
    }
    *resc
}


acSetRescSchemeForCreate  
{
*resc = ""
    if ($objPath like "*.img.csv") { *role =  "image_processing" }
    else {*role = ""}
    if (*role != "") {
        *resc  = resc_from_compute_role( *role )
    }
    if (*resc != "") {
        msiSetDefaultResc("*resc","forced");
    }
    else {
        msiSetDefaultResc("demoResc","null");
    }
}

