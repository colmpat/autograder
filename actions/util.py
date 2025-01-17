import sys
import tomlkit

class OutputLimitExceeded(Exception):
    pass

def fatal(s):
    print_red(s, '\n')
    sys.exit(-1)


def print_green(s, e=''):
    print('\033[92m' + s + '\033[0m', end=e, flush=True)


def print_red(s, e=''):
    print('\033[91m' + s + '\033[0m', end=e, flush=True)


def print_justified(s, longest):
    print(s, end='')
    for i in range (longest - len(s)):
        print(' ', end='')


def failed(tc_result):
    if tc_result['score'] == 0:
        return True
    return False


def format_pass_fail(tc_result):
    name = tc_result['test']
    rubric = tc_result['rubric']
    score = tc_result['score']

    # Pad formatted string out to same length as full credit
    # so that individual test cases and the total are column-aligned
    max_len = len(f'{name}({rubric}/{rubric}) ')
    this_fmt = f'{name}({score}/{rubric}) '
    padding = max_len - len(this_fmt)
    for i in range(padding):
        this_fmt += ' '

    return this_fmt


def load_toml(path):
    try:
        with open(path) as f:
            data = f.read()
            return tomlkit.parse(data)
    except FileNotFoundError as fnf:
        fatal(f'File not found: {path}. Suggest "git pull" in tests repo')
    except Exception as e:
        fatal(f'Failed to parse {path}: ' + str(e))

def make_repo_path(project, student):
    return f'{project}-{student}'

def project_from_cwd(cwd):
    # if the current directory is named like a given project (project-username),
    # use that as the project name
    # eg. if cwd is '/path/to/project1-phpeterson', return 'project1'
    # otherwise, use the current directory name
    # eg. if cwd is '/path/to/project1', use 'project1'
    i = cwd.name.find('-')
    return cwd.name if i == -1 else cwd.name[:i]
