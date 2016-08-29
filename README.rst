Fuel nailgun extenstion for cluster upgrade
===========================================

This extension for Nailgun provides API handlers and logic for
cluster upgrading. This extension used by the fuel-octane project.

Instalation
-----------
After installing ``fuel-nailgun-extension-cluster-upgrade`` package run:
 #. ``nailgun_syncdb`` - migrate database
 #. restart nailgun service

Transformer configuration
-------------------------

Every transformation manager has default config that hardcoded, but
you can overwrite this config with your own to add your
transformations from your extensions. This could be done by extending
``nailgun/settings.yaml`` file.

**Example**

::
   CLUSTER_UPGRADE:
     transformations:
       my_shiny_metall_transformation:
         9.0: [first_transformation, second_transformation]
         6.1: [test_transformation]

   ...
