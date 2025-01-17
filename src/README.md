# Instructions for creating new stubs

1. Create a paths.py to represent your local setup. Paths_template.py shows all the vars that need to be set.
2. Copy src folder into your sdk_mods folder. Probably rename it something like bl_py_stubs.
3. From in game (BL2 or TPS), `pyexec bl_py_stubs/game_class_defs.py`. This will create and write the pickled Python objects that store all of the info we need.
4. Repeat for the other game.
5. From local Python instance, run common_class_defs.py to create the common version of the same thing.
6. Finally, run write_stubs.py to convert the pickled info objects into usable stubs.