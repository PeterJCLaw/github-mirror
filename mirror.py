#!/usr/bin/env python

from __future__ import print_function

import argparse
from functools import partial
from hammock import Hammock
import logging
import os
import os.path
from queue import Queue, Empty
from subprocess import check_output
from threading import Thread

def ensure_dir(*path_pieces):
    path = os.path.join(*path_pieces)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

class BaseRepo(object):
    def __init__(self, int_dir, url, name):
        self._int_dir = int_dir
        self._url = url
        self._name = name

    def mirror(self, base_dir):
        base_dir = ensure_dir(base_dir, self._int_dir)
        name = self._name + '.git'
        args = ['git', 'clone', '--mirror', self._url]
        logging.debug(args, base_dir)
        #check_output(args, cwd=base_dir)
        kind = type(self).__name__.lower()
        logging.info("Cloned {0} {1}".format(kind, self._name))

    def __repr__(self):
        kind = type(self).__name__
        return "{0}({1}, {2})".format(kind, self._url, self._name)

class Gist(BaseRepo):
    def __init__(self, url, id_):
       super(Gist, self).__init__('gists', url, id_)

class Repo(BaseRepo):
    def __init__(self, url, name):
       super(Repo, self).__init__('repos', url, name)

def do_multiple(n_threads, actions):
    if not actions:
        return

    q = Queue()
    for action in actions:
        q.put(action)

    def worker():
        while True:
            try:
                action = q.get_nowait()
            except Empty:
                return
            else:
                try:
                    action()
                except:
                    logging.exception("Failed executing '%s'", action)
                finally:
                    q.task_done()

    # Build our pool
    threads = []
    for n in range(n_threads):
        t = Thread(target=worker, name='worker-{}'.format(n))
        threads.append(t)
        t.start()

    # Wait for completeion
    q.join()

    # Tidy our threads
    for t in threads:
        t.join()

def get_args():
    parser = argparse.ArgumentParser(description='Mirror repositories from github.')
    parser.add_argument('username', help='The user to mirror the repos from')
    parser.add_argument('dir', default='.', nargs='?',
                        help='The directory to put the clones into')

    parser.add_argument('--log', default='INFO',
                        help='The logging level to set (in the logging module).'
                             ' Defaults to INFO.')

    args = parser.parse_args()
    return args

def get_repos_and_gists(user):
    gists = user.gists.GET().json()
    for gist in gists:
        id_ = gist.get('id')
        pull_url = gist.get('git_pull_url')
        yield Gist(pull_url, id_)

    repos = user.repos.GET().json()
    for repo in repos:
        name = repo.get('name')
        clone_url = repo.get('clone_url')
        yield Repo(clone_url, name)

def main():
    args = get_args()

    log_level = getattr(logging, args.log.upper())
    logging.basicConfig(level=log_level)

    github = Hammock('https://api.github.com')
    user = github.users(args.username)

    base_dir = args.dir
    clone_actions = [partial(repo.mirror, base_dir)
                        for repo in get_repos_and_gists(user)]

    logging.info("About to clone %d repos for user '%s'.",
                 len(clone_actions), args.username)

    do_multiple(4, clone_actions)

    logging.info("Done to cloning %d repos for user '%s'.",
                 len(clone_actions), args.username)

if __name__ == '__main__':
    main()
