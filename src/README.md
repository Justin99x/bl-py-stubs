# Instructions for creating new stubs

1. Create a paths.py to represent your local setup. Paths_template.py shows all the vars that need to be set.
2. In each game (BL2 and TPS), set `Binaries\Win32\Plugins\unrealsdk.user.toml` to have 
    ```
    [mod_manager]
    extra_folders = [
    "path\\to\\project\\bl-py-stubs",
    ]
    ```
3. From in game (BL2 or TPS), type `bps` into console to trigger the custom command. This will create and write the pickled Python objects that store all of the info we need.
4. Repeat for the both games.
5. From local Python instance, run common_class_defs.py to create the common version of the same thing.
6. Finally, run write_stubs.py to convert the pickled info objects into usable stubs.