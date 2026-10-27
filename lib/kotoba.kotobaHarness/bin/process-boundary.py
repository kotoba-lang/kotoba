"""Child-process environment mechanisms shared by both native routes."""
import os
import subprocess


def clean_env(source=None, **grants):
    source = os.environ if source is None else source
    return dict({k: v for k, v in source.items()
                 if not k.startswith(('KEXE_', 'OPENROUTER_'))}, **grants)


class BrowserProcesses:
    """Keep the pinned driver's browser launch free of model credentials.

    The driver has no environment parameter. A module-local subprocess facade
    supplies one without changing the driver files or global os.environ.
    """
    def __getattr__(self, name):
        return getattr(subprocess, name)

    def Popen(self, *args, **kwargs):
        kwargs['env'] = clean_env(kwargs.get('env'))
        return subprocess.Popen(*args, **kwargs)
