import sys
import ctypes
import os
import subprocess
import errno
import logging


log = logging.getLogger('Namespace')

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


# bits/sched.h linux/sched.h
CLONE_CSIGNAL = 0x000000FF
CLONE_VM = 0x00000100
CLONE_FS = 0x00000200
CLONE_FILES = 0x00000400
CLONE_SIGHAND = 0x00000800
CLONE_NEWNS = 0x00020000
CLONE_STOPPED = 0x02000000
CLONE_NEWUTS = 0x04000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
SIGCHLD = 17

STACK_SIZE = 1024*1024
# Keep a reference to created stacks to avoid garbage collecting
_STACKS = {}


class NamespaceException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class Namespace(object):
    _libc = ctypes.CDLL("libc.so.6", use_errno=True)

    def __init__(self, init_function=None, **kw_args):
        self.pid = -1
        self.proc = None
        self.kw_args = kw_args
        if init_function is None:
            init_function = self._init_process_func
        self._new_usr_pid_ns(init_function)

    def _init_process_func(self):
        proc = subprocess.Popen(**self.kw_args)
        exit_status = 0
        # TODO pipe select and handler for SIGCHLD
        while True:
            try:
                # Wait for all children
                pid, status = os.wait()
            except OSError as e:
                if e.errno == errno.ECHILD:
                    break  # No more children
                sys.exit(1)  # Unhandled OSError
            if os.WIFEXITED(status):
                exit_status += os.WEXITSTATUS(status)

        return sys.exit(exit_status)

    def Popen(self, **kw_args):
        pass

    def add_proc(self, proc):
        pass

    def terminate(self):
        # send a message to the init process over the pipe
        pass

    def _new_usr_pid_ns(self, ns_init_function):
        # Create a stack
        stack = ctypes.c_char_p(b" " * STACK_SIZE)
        # Append to the global stack list
        _STACKS[self] = stack

        # Convert function to c type returning an integer.
        f_c = ctypes.CFUNCTYPE(ctypes.c_int)(ns_init_function)

        # As this is a stack, the end is the top
        stack_top = ctypes.c_void_p(
            ctypes.cast(stack, ctypes.c_void_p).value + STACK_SIZE
        )

        self.pid = self._libc.clone(
            f_c, stack_top,
            CLONE_NEWUSER | CLONE_NEWPID | SIGCHLD,
            None
        )
        if self.pid < 0:
            log.warning("clone error: %d", ctypes.get_errno())
            raise NamespaceException(os.strerror(ctypes.get_errno()))

    def wait(self):
        os.waitpid(self.pid, 0)


if __name__ == '__main__':
    import textwrap
    args = [
        sys.executable,
        '-c',
        textwrap.dedent('''
                        import subprocess
                        import sys
                        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
                        ''')
    ]

    ns = Namespace(args=args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ns.wait()
    print("done")
