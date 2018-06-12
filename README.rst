========================
Team and repository tags
========================

.. image:: https://governance.openstack.org/tc/badges/fuel-nailgun-extension-cluster-upgrade.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

.. Change things from this point on

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
you can overwrite this config with your own transformations
extensions. This could be done by extending ``nailgun/settings.yaml``
file.

**Example**

::

   CLUSTER_UPGRADE:
     transformations:
       cluster:
         7.0: [transform_vips]
         9.0: [first_transformation, second_transformation]

   ...

In extension you should define a entrypoint is such way:

::

   nailgun.cluster_upgrade.transformations.cluster.7.0 =
      transform_vips = my_project.transformations:transform_cluster_vips

on first line we have entripoint name where

* ``nailgun.cluster_upgrade.transformations`` - namespace where all transformations defined.
* ``cluster`` - name of object which data transformed
* ``7.0`` - cluster version where these transformations should happen

on the second line

* ``transform_vips`` - unique transformation name that you can use in configuration file or in transformation manager
* ``my_project.transformations`` - module name
* ``transform_cluster_vips`` - transformer function name


Transformation function must take only one argument - data to
transform. When you call ``manager.apply(from_version, to_version,
data)`` all transformer functions ordered by a version called one by
one, and output of one transformer used as input to the other.

In out example calling ``cluster_manager.apply('6.0', '9.1', data)``
will call three functions ``transform_vips``,
``first_transformation``, ``second_transformation``.
