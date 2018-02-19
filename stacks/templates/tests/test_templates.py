import os
import pytest


def discover_templates():
    """Get all files that contain templates. Returns a list of abs paths."""
    p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(p)

    # files = [f[:-3] for f in os.listdir(p) if f != '__init__.py' and f.endswith('.py')]
    files = [os.path.join(p, f) for f in os.listdir(p) if f != '__init__.py' and f.endswith('.py')]
    return files


def load_module(module_path):
    """Dynamically load a module from an abs path and return it"""
    module = dict()
    with open(module_path) as f:
        exec(f.read(), module)
    return module


# discover all templates
templates = discover_templates()
ids = [os.path.basename(f)[:-3] for f in templates]


@pytest.mark.parametrize('template', templates, ids=ids)
def test_template(template):
    # load the module & check if there is a stack function
    module = load_module(module_path=template)
    assert 'stack' in module.keys(), 'stack function not found in template {}'.format(template)

    # execute the stack function.
    stack = module['stack']()

    # convert to json
    stack.to_json()
