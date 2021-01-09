import os
from pyshortcuts.windows import make_shortcut

store_dir = r"C:\\"
repo_dir = os.path.join(store_dir, 'oeps')
path_file = os.path.join(repo_dir, 'main.py')
path_icon = os.path.join(repo_dir, 'icon.ico')
make_shortcut(path_file, name ='OEPS_2', working_dir = repo_dir,
                        icon = path_icon, terminal = False)