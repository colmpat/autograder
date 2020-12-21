#!/usr/bin/env python3

import argparse
import os
import string
import subprocess
import sys
import toml


def cmd_exec(args, wd=None):
    return subprocess.run(args, capture_output=True, timeout=10, cwd=wd)


def cmd_exec_rc(args):
    proc = cmd_exec(args)
    return proc.returncode


def cmd_exec_capture(args, wd=None, path=None):
    proc = cmd_exec(args, wd)
    if (path):
        try:
            # capture output written to path
            f = open(path, 'r')
            output = f.read()
            f.close()
        except FileNotFoundError:
            return ''
    else:
        # capture output written to stdout
        output = proc.stdout.decode('utf-8')
    return output.rstrip('\n')


def print_green(s, e=''):
    print('\033[92m' + s + ' \033[0m', end=e)


def print_red(s, e=''):
    print('\033[91m' + s + ' \033[0m', end=e)


class Config:
    def __init__(self, d):
        self.action = d['action']           # required
        self.credentials = d['credentials'] # required
        self.digital = d.get('digital')     # optional til Digital projects
        self.local = d.get('local')         # could get students or local
        self.org = d['org']                 # required
        self.project = d['project']         # required
        self.project_tests = os.path.join(os.getcwd(), 'tests', self.project)
        self.students = d.get('students')   # could get students or local
        self.verbose = d['verbose']         # optional, defaults to False

    def parse_args(fname):
        # .toml file contains defaults. Command line args can override
        with open(fname) as f:
            defaults = toml.load(f)
        p = argparse.ArgumentParser()
        p.add_argument('action', type=str, choices=['clone', 'test'])
        p.add_argument('-c', '--credentials', choices=['https', 'ssh'], help='Github auth method',
            default=defaults.get('credentials', None))
        p.add_argument('-d', '--digital', help='Path to digital.jar',
            default=defaults.get('digital', None))
        p.add_argument('-l', '--local', help='Local directory to test',
            default=defaults.get('local', None))
        p.add_argument('-o', '--org', help='Github Classroom Organization',
            default=defaults.get('org', None))
        p.add_argument('-p', '--project', help='Project name',
            default=defaults.get('project', None))
        p.add_argument('-s', '--students', nargs='+', type=str, help='Student Github IDs',
            default=defaults.get('students', None))
        p.add_argument('-v', '--verbose', action='store_true', help='Print actual and expected output',
            default=defaults.get('verbose', False))
        return vars(p.parse_args())


class TestCase:
    trans_table = str.maketrans(dict.fromkeys(string.whitespace))
    def __init__(self, cfg, d):
        self.cmd_line = []
        for i in d['input']:
            if '$project_tests' in i:
                param = i.replace('$project_tests', cfg.project_tests)
            elif '$project' in i:
                param = i.replace('$project', cfg.project)
            elif '$digital' in i:
                param = i.replace('$digital', cfg.digital)
            else:
                param = i
            self.cmd_line.append(param)
        self.expected = d['expected']
        self.name = d['name']
        self.output = d.get('output', 'stdout')
        self.rubric = d['rubric']
        self.verbose = cfg.verbose


    def get_actual(self, local):
        if self.output == 'stdout':
            # get actual output from stdout
            return cmd_exec_capture(self.cmd_line, local)
        else:
            # ignore stdout and get actual output from the specified file
            path = os.path.join(local, self.output)
            return cmd_exec_capture(self.cmd_line, local, path)


    def match_expected(self, actual):
        # compare case-insensitive, ignoring whitespace
        # I'm queasy about ignoring whitespace, but it is what maketest did
        loose_act = actual.lower().translate(TestCase.trans_table)
        loose_exp = self.expected.lower().translate(TestCase.trans_table)
        if self.verbose:
            print(f"actual\n{loose_act}\nexpected\n{loose_exp}")
        return loose_act == loose_exp


def load_tests(cfg):
    tests_file = os.path.join(cfg.project_tests, cfg.project + '.toml', )
    with open(tests_file) as f:
        toml_input = toml.load(f)
    test_cases = []
    for t in toml_input['tests']:
        test_cases.append(TestCase(cfg, t))
    return test_cases


class Repo:
    def __init__(self, cfg, **kwargs):
        # calculate the local and remote for this repo
        student = kwargs.get('student')
        if student:
            pg = cfg.project + '-' + student
            self.local = os.path.join('github.com', cfg.org, pg)
            # set up remote repo for clone
            if cfg.credentials == 'https':
                self.remote = 'https://github.com/'
            elif cfg.credentials == 'ssh':
                self.remote = 'git@github.com:/'
            self.remote += cfg.org + '/' + pg + '.git'
        # allow -l/--local to override the local directory calculated above
        if kwargs.get('local'):
            self.local = kwargs['local'].rstrip('/')
        self.label = self.local.split('/')[-1]
        self.results = []
        self.verbose = cfg.verbose


    def clone(self):
        if self.remote is None:
            raise Exception(self.label + ' no remote to clone')
        if os.path.isdir(self.local):
            return 0  # don't ask git to clone if local already exists
        print(self.local)
        return cmd_exec_rc(['git', 'clone', self.remote, self.local])


    def build(self):
        return cmd_exec_rc(['make', '-C', self.local])


    def test_one(self, test_case):
        score = 0
        actual = test_case.get_actual(self.local)
        if test_case.match_expected(actual):
            score = test_case.rubric

        # record score for later printing
        result = {'test': test_case, 'score': score}
        self.results.append(result)


    def test(self, test_cases):
        for tc in test_cases:
            self.test_one(tc)


    def print_results(self, longest):
        print(self.label, end='')
        for n in range(longest - len(self.label)):
            print(' ', end='')

        earned = 0
        avail = 0
        for r in self.results:
            rubric = r['test'].rubric
            avail += rubric
            if r['score'] == 0:
                print_red(r['test'].name)
            else:
                earned += rubric
                print_green(r['test'].name)

        print(f"{earned}/{avail}")


def main():
    args = Config.parse_args('config.toml')
    cfg = Config(args)
    test_cases = load_tests(cfg)

    # Build list of repos to run, either from local or list of students
    repos = []
    if cfg.local:
        # One local repo
        if not os.path.isdir(cfg.local):
            raise Exception(cfg.local + ' is not a directory')
        repo = Repo(cfg, local=cfg.local)
        repos.append(repo)
    elif cfg.students:
        # Make repo list from student list
        for s in cfg.students:
            repo = Repo(cfg, student=s)
            repos.append(repo)
    else:
        print('no local directory or students specified')
        return -1

    # Calc column width for justified printing
    longest = 0;
    for r in repos:
        l = len(r.label)
        if l > longest:
            longest = l
    longest += 1

    # Run all of the repos, either clone or test
    for repo in repos:
        try:
            if cfg.action == 'clone':
                repo.clone()
            elif cfg.action == 'test':
                repo.build()
                repo.test(test_cases)
                repo.print_results(longest)
        except Exception as e:
            print_red(repo.label + ' ' + str(e), '\n')
            continue


if __name__ == "__main__":
    main()
