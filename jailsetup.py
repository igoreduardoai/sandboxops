"""Trusted namespace setup. This process is single-threaded and exits after the child.

User code is not interpolated into a shell. Paths arrive as argv from sandbox.py.
"""
import ctypes
import os
import resource
import sys

CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
MS_REC = 16384
MS_PRIVATE = 1 << 18
MS_BIND = 4096
MS_RDONLY = 1
MS_REMOUNT = 32
MNT_DETACH = 2


def fail(message):
    sys.stderr.write("sandbox-setup: " + message + "\n")
    sys.exit(86)


def must(libc, name, rc):
    if rc != 0:
        err = ctypes.get_errno()
        fail(f"{name} {err} {os.strerror(err)}")


def libc_unshare(libc, flags):
    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int
    must(libc, "unshare", libc.unshare(flags))


def map_ids(uid, gid):
    with open("/proc/self/setgroups", "w", encoding="ascii") as handle:
        handle.write("deny\n")
    with open("/proc/self/uid_map", "w", encoding="ascii") as handle:
        handle.write(f"0 {uid} 1\n")
    with open("/proc/self/gid_map", "w", encoding="ascii") as handle:
        handle.write(f"0 {gid} 1\n")


def enter_root(libc, template, taskdir, work):
    must(libc, "private", libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None))
    must(libc, "work", libc.mount(b"tmpfs", work.encode(), b"tmpfs", 0, b"size=64m"))
    for name in ("usr", "lib", "lib64"):
        source = os.path.join(template, name)
        dest = os.path.join(work, name)
        os.makedirs(dest, exist_ok=True)
        must(libc, "bind " + name, libc.mount(source.encode(), dest.encode(), None, MS_BIND, None))
        must(libc, "ro " + name, libc.mount(None, dest.encode(), None, MS_BIND | MS_REMOUNT | MS_RDONLY, None))
    for name in ("tmp", "task", "proc", "oldroot"):
        os.makedirs(os.path.join(work, name), exist_ok=True)
    must(libc, "task", libc.mount(taskdir.encode(), os.path.join(work, "task").encode(), None, MS_BIND, None))
    must(libc, "ro task", libc.mount(None, os.path.join(work, "task").encode(), None, MS_BIND | MS_REMOUNT | MS_RDONLY, None))
    must(libc, "tmp", libc.mount(b"tmpfs", os.path.join(work, "tmp").encode(), b"tmpfs", 0, b"size=16m,mode=1777"))
    os.chdir(work)
    must(libc, "pivot", libc.pivot_root(b".", b"oldroot"))
    os.chroot(".")
    os.chdir("/")
    must(libc, "umount", libc.umount2(b"/oldroot", MNT_DETACH))
    try:
        os.rmdir("/oldroot")
    except OSError:
        pass
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 2**20, 10 * 2**20))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    os.execve("/usr/bin/python3", ["python", "-I", "/task/task.py"], {"PATH": "/usr/bin", "LC_ALL": "C"})


def main():
    if len(sys.argv) != 4:
        fail("usage")
    template, taskdir, work = sys.argv[1:]
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    libc.pivot_root.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    libc.pivot_root.restype = ctypes.c_int
    libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
    libc.umount2.restype = ctypes.c_int
    host_uid = os.getuid()
    host_gid = os.getgid()
    libc_unshare(libc, CLONE_NEWUSER)
    try:
        map_ids(host_uid, host_gid)
    except OSError as exc:
        fail(f"id map {exc.errno}")
    libc_unshare(libc, CLONE_NEWNET | CLONE_NEWPID)
    pid = os.fork()
    if pid != 0:
        _pid, status = os.waitpid(pid, 0)
        if os.WIFSIGNALED(status):
            sig = os.WTERMSIG(status)
            sys.stderr.write(f"sandbox-signal: {sig}\n")
            sys.exit(128 + sig)
        sys.exit(os.WEXITSTATUS(status))
    libc_unshare(libc, CLONE_NEWNS)
    enter_root(libc, template, taskdir, work)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(type(exc).__name__)
