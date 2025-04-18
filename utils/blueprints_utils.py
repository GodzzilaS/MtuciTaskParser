import importlib.util
import os
import rainbow


def absolute_path(path):
    return os.path.join(os.getcwd(), path)


def import_module_from_file(full_path_to_module):
    module = None

    try:
        module_dir, module_file = os.path.split(full_path_to_module)
        module_name, module_ext = os.path.splitext(module_file)
        spec = importlib.util.spec_from_file_location(module_name, full_path_to_module)
        module = spec.loader.load_module(module_name)
    except Exception as ec:
        print(ec)

    finally:
        return module


def inject(path, app):
    for root, dirs, files in os.walk(absolute_path(path)):
        for file in files:
            if file.endswith('.py'):
                module_path = os.path.join(root, file)
                module = import_module_from_file(module_path)

                try:
                    app.register_blueprint(module.__dict__['blueprint'])
                    print(rainbow.paint(f'#70B8FF * BLUEPRINT: #50C878{module.__dict__["blueprint"].name}'))
                except AssertionError as e:
                    print(rainbow.paint(' * BLUEPRINT_ERROR: ' + str(e), color='#F07427'))
                except Exception as e:
                    print(rainbow.paint(' * ERROR: ' + str(e), color='#F07427'))
                    raise Exception(f"No blueprint found in {module_path}")
