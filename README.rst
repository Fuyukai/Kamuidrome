Kamuidrome
==========

.. image:: demo.gif
    :alt: Demo asciinema
    :target: https://asciinema.org/a/emNSBAOMSGAwgsCxsh6Fovmw7

Kamuidrome is a Minecraft modpack creation helper that integrates directly with Prism Launcher.
Kamuidrome is currently geared entirely towards modpack developers, *not* modpack users. Modpack
users should use the exported ``mrpack`` packs instead.

Kamuidrome comes with first-class support for `Sinytra Connector <https://modrinth.com/mod/connector>`_,
meaning you can manage Fabric mods in a Forge workspace without issues.

Installation
------------

Kamuidrome is available on PyPI, and can be installed with `pipx <https://pipx.pypa.io/stable/installation/>`_:

.. code-block:: fish

    $ pipx install kamuidrome

Getting Started
---------------

A new, empty modpack can be created using the ``kamuidrome init`` subcommand. This will 
interactively guide you through setting up your ``pack.toml`` and generate a skeleton file structure
for you.

::

    $ kamuidrome init --git
    Pack name: My Awesome Modpack
    Minecraft version: 1.20.1
    Pack version (0.1.0): 0.1.0
    Modloader [legacyforge/neoforge/fabric/quilt]: fabric
    Modloader version (leave empty for auto): 0.15.3

Adding Mods
-----------

Modrinth mods can be added to your modpack in one of three ways:

- Using ``kamuidrome add [-s/--search]`` to add a mod via a search query. This will add mods either
  based on a direct name match (most commonly) or allow you to select the mod you mean.

- Using ``kamuidrome add [-p/--project-id]`` to add the latest version of a specific project, based
  on its *Modrinth project ID*.

- Using ``kamuidrome add [-V/--version-id]`` to add a specific version of a specific project.

When adding a mod, dependencies will be automatically resolved and downloaded if the author has
provided the appropriate metadata on Modrinth.

::

    $ kamuidrome add -s "Big Globe"
    successful match: Big Globe / xsng1aJf
    selected version 3.12.0 for Big Globe
    selected version 0.91.0+1.20.1 for [1.20.1] Fabric API 0.91.0+1.20.1
    skipping Big Globe download as it exists already
    [1.20.1] Fabric API 0.91.0+1.20.1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    Downloading mods...               ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Mod Caching
~~~~~~~~~~~

Mods are automatically cached in your ``$XDG_CACHE_HOME`` directory, meaning that specific mod 
versions will only ever be downloaded once. 

Adding Local Mods
~~~~~~~~~~~~~~~~~

Any mods in the ``mods/`` directory are considered "local mods", and will be ignored by 
``kamuidrome`` outside of deployments and exporting. You can use this for mods that aren't available
on Modrinth (provided you obey copyright requirements).

Sinytra Connector
~~~~~~~~~~~~~~~~~

When using a ``legacyforge`` or ``neoforge`` pack with ``sinytra_compat`` enabled, all mods with
a ``fabric`` category will be valid for installation. In the case of mods that have both a Fabric
and a Forge version available, the Forge version will *always* be selected, even if the Fabric
version is newer.

Fabric API dependencies will automatically be rewritten to Forgified Fabric API when adding mods
with the command line. 

Installing Indexed Mods
-----------------------

Whilst ``kamuidrome add`` *adds* mods to the index, other developers need to be able to install all
of the mods when checking out the repository. The ``kamuidrome download`` command will download all
mods in the modpack index and store them in the mod cache.

::

    $ kamuidrome download                                                                                                                                                                                                                ↵ 2
    Big Globe 3.12.0                  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    [1.20.1] Fabric API 0.91.0+1.20.1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    Downloading mods...               ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Listing Indexed Mods
--------------------

The ``kamuidrone list`` command can be used to list all mods currently installed in the index.

Updating Mods
-------------

Mods can be automatically updated with the ``kamuidrome update`` command. This will fetch version
information for all mods in the mod index and update all non-pinned mods to their latest version.

:: 

    $ kamuidrome update
    selected version 3.12.0 for Big Globe
    selected version 0.91.0+1.20.1 for [1.20.1] Fabric API 0.91.0+1.20.1
    selected version 0.91.0+1.20.1 for Fabric API
    Fetching mod info ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    skipping Big Globe download as it exists already
    skipping Fabric API download as it exists already
    Downloading mods... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Pinning Mods
~~~~~~~~~~~~

If a mod you have in your index can't be updated (possibly due to incompatibility or bugs) you can
pin the version using the ``kamuidrome pin`` command or by editing the ``pinned`` field in the
index manually.

::

    $ kamuidrome pin "Big Globe"
    pinned mod Big Globe to version 3.12.0

Updates for pinned mods will still be downloaded, but the metadata in the mod index will not be
changed.

Prism Integration
-----------------

Kamuidrome has Prism Launcher integration as a first class feature via the power of symbolic links.
You can automatically deploy a modpack to an instance with the ``kamuidrome deploy`` command, which
will symlink data from your download mod cache and local pack directory.

This is a more flexible approach than ones used by other pack builders (such as Packwiz); for 
example, you can edit configurations in-game and have the changes saved to your ``config`` 
directory in your pack without needing to synchronise.

::

    $ kamuidrome deploy "test pack"
    cleaning up symlinks from index...
    linked included dir /home/lura/.local/share/PrismLauncher/instances/test pack/.minecraft/config
    linked managed mod /home/lura/.local/share/PrismLauncher/instances/test pack/.minecraft/mods/Big Globe-3.12.0-MC1.20.1.jar
    linked managed mod /home/lura/.local/share/PrismLauncher/instances/test pack/.minecraft/mods/fabric-api-0.91.0+1.20.1.jar

Please note that this will *delete* any data in the instance's ``config`` directory, or any other
synchronised directories (outside of jars in the ``mods/`` directory) before creating the symbolic
links.

You can store an instance name in the ``localpack.toml`` file (this should be added to your 
gitignore) so that you don't need to type the instance name when running the ``deploy`` command.

.. code-block:: toml
    
    # example ``localpack.toml`` file
    instance_name = "test pack"

Adding Extra Directories
~~~~~~~~~~~~~~~~~~~~~~~~

Extra directories for both deployment and export can be added with the ``include_directories``
key in your ``pack.toml``::

    include_directories = [
       "kubejs",
    ]

These directories will be symlinked to your instance folder and included in the generated ``mrpack``.
