"""
Construct FreeBSD ports templates given the name of a Subversion
working directory.

$Id$

Copyright (C) 2012-2013  Internet Systems Consortium ("ISC")

Permission to use, copy, modify, and distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS.  IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

import sys
import os
import subprocess
import errno
import glob
import shutil

try:
  svndir = sys.argv[1]
except IndexError:
  sys.exit("Usage: %s subversion-working-directory" % sys.argv[0])

if not os.path.isdir(svndir):
  sys.exit("Usage: %s subversion-working-directory" % sys.argv[0])

svnversion = subprocess.check_output(("svnversion", "-c", svndir)).strip().split(":")[-1]

if not svnversion.isdigit():
  sys.exit("Sources don't look pristine, not building (%r)" % svnversion)

branch  = os.path.basename(svndir.rstrip(os.path.sep))

if branch != "trunk" and (branch[:2] != "tk" or not branch[2:].isdigit()):
  sys.exit("Could not parse branch from working directory name, not building (%r)" % branch)

version = "0." + svnversion
tarname = "rpki-%s-r%s" % (branch, svnversion)
tarball = tarname + ".tar.xz"
url     = "http://download.rpki.net/" + tarball

portsdir = os.path.abspath("freebsd-ports")

if os.path.isdir(portsdir):
  shutil.rmtree(portsdir)

shutil.copytree(os.path.join(svndir, "buildtools", "freebsd-skeleton"), portsdir)

base_rp = os.path.join(portsdir, "rpki-rp")
base_ca = os.path.join(portsdir, "rpki-ca")

formatdict = { "SVNVERSION" : svnversion }

for port in ("rpki-rp", "rpki-ca"):

  fn = os.path.join(portsdir, port, "Makefile")
  with open(fn, "r") as f:
    template = f.read()
  with open(fn, "w") as f:
    f.write(template % formatdict)

subprocess.check_call(("make", "makesum", "DISTDIR=" + portsdir), cwd = base_rp)
subprocess.check_call(("make", "makesum", "DISTDIR=" + portsdir), cwd = base_ca)

trust_anchors = [os.path.basename(fn)
                 for fn in subprocess.check_output(("tar", "tf", os.path.join(portsdir, tarball))).splitlines()
                 if "/rcynic/sample-trust-anchors/" in fn and fn.endswith(".tal")]

with open(os.path.join(base_rp, "pkg-plist"), "w") as f:

  f.write('''\
bin/find_roa
bin/hashdir
bin/print_roa
bin/print_rpki_manifest
bin/rcynic
bin/rcynic-cron
bin/rcynic-html
bin/rcynic-svn
bin/rcynic-text
bin/rtr-origin
bin/scan_roas
bin/validation_status
@unexec if cmp -s %D/etc/rcynic.conf.sample %D/etc/rcynic.conf; then rm -f %D/etc/rcynic.conf; fi
etc/rcynic.conf.sample
@exec if [ ! -f  %D/etc/rcynic.conf ] ; then cp -p %D/%F %D/etc/rcynic.conf; fi
''')

  for trust_anchor in sorted(trust_anchors):
    f.write("etc/rpki/trust-anchors/%s\n" % trust_anchor)

  f.write('''\
@dirrm etc/rpki/trust-anchors
@dirrmtry etc/rpki
@dirrm www/apache22/data/rcynic
@cwd /
@exec install -d -o root   -g wheel  %D/var/rcynic
@exec install -d -o rcynic -g rcynic %D/var/rcynic/data
@dirrm var/rcynic/data
@exec install -d -o rcynic -g rcynic %D/var/rcynic/rpki-rtr
@dirrm var/rcynic/rpki-rtr/sockets
@dirrm var/rcynic/rpki-rtr
@dirrm var/rcynic
''')

# "USE_GNOME=" gets rid of annoying whining due to empty or
# non-existent pkg-plist.  The (direct) Gnome dependency doesn't
# matter while constructing the port skeleton, so it's simplest just
# to disable it for this one command.

subprocess.check_call(("make", "DISTDIR=" + portsdir, "USE_GNOME="), cwd = base_ca)

tempdir = os.path.join(base_ca, "work", "temp-install", "")

subprocess.check_call(("make", "install", "DESTDIR=" + os.path.abspath(tempdir)),
                      cwd = os.path.join(base_ca, "work", tarname))

with open(os.path.join(base_ca, "pkg-plist"), "w") as f:

  dont_remove = ("usr", "etc", "bin", "var", "lib", "sbin", "share", "lib/python2.7", "lib/python2.7/site-packages")

  usr_local = None

  for dirpath, dirnames, filenames in os.walk(tempdir, topdown = False):
    dn = dirpath[len(tempdir):]

    if dn.startswith("usr/local"):
      if not usr_local and usr_local is not None:
        f.write("@cwd\n")
      usr_local = True
      dn = dn[len("usr/local/"):]
    else:
      if usr_local:
        f.write("@cwd /\n")
      usr_local = False

    if not dirnames and not filenames:
      f.write("@exec mkdir -p %%D/%s\n" % dn)

    for fn in filenames:
      if fn == "rpki.conf.sample":
        f.write("@unexec if cmp -s %%D/%s/rpki.conf.sample %%D/%s/rpki.conf; then rm -f %%D/%s/rpki.conf; fi\n" % (dn, dn, dn))
      f.write(os.path.join(dn, fn) + "\n")
      if fn == "rpki.conf.sample":
        f.write("@exec if [ ! -f %%D/%s/rpki.conf ] ; then cp -p %%D/%s/rpki.conf.sample %%D/%s/rpki.conf; fi\n" % (dn, dn, dn))

    if dn and dn not in dont_remove:
      f.write("@dirrm %s\n" % dn)

subprocess.check_call(("make", "clean"), cwd = base_ca)

for port in ("rpki-rp", "rpki-ca"):
  subprocess.check_call(("tar", "czf", "%s-port.tgz" % port, port), cwd = portsdir)
