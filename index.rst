:tocdepth: 1

.. sectnum::

.. TODO: Delete the note below before merging new content to the main
   branch.

.. note::

   **This technote is a work-in-progress.**

Abstract
========

We present a mechanism for exposing user files via WebDAV, so that there
are ways to get to the files that are not dependent on having a running
RSP.

We have a requirement for users to be able to read and write their files
from their desktop environments.  One obvious use-case is so that users
can use their favorite editors without requiring that we provide all
possible editors in the RSP environment.  Many of these (e.g. VSCode)
would require us to forward a graphical connection to a virtualized user
desktop (presumably by X or VNC), which opens up a new attack surface on
the RSP lab, as well as the associated maintenance issues.

WebDAV seems like a reasonable mechanism to allow file manipulation; it
is, after all, a protocol extension to HTTP, and we are by definition
providing HTTP access to RSP resources

Approaches Considered
=====================

This is not a new idea; user file access to resources in the RSP has
been something we've wanted for a long time.  There have been at least
three ideas for how to provide a WebDAV-based user file server.

Nginx Extensions
----------------

One approach was started by Brian Van Klaveren several years ago.  His
idea was to take the built-in rudimentary WebDAV support in Nginx,
extend that with https://github.com/arut/nginx-dav-ext-module (which
adds the rest of the WebDAV verbs, turning it into a complete WebDAV
implementation.)  Atop that, Brian would install
https://github.com/lsst-dm/legacy-davt which would add user
impersonation, allowing the Nginx server to serve files as the
requesting user.

This is not *prima facie* a bad idea.  We rely on Nginx for our
ingresses in the RSP, and Nginx module creation, while hideous, is
thoroughly documented.  Granted, to avoid the hideousness, Brian had
decided to implement his module in Lua rather than C, which in turn
leads to a fairly hard requirement to use the OpenResty Nginx fork
(because adding Lua support by hand is extremely tricky).  That seemed
an odd decision, since most of Brian's code uses the FFI, and it's just
Lua using C bindings to do system calls to change the various user IDs
in effect.

In any event, it didn't matter.  That's because we need to care about
more than the primary user and group, which are accessible via
``setfsuid()`` and ``setfsgid()`` respectively.  We also need to care
about the user's supplementary groups, and we can't handwave that away
because supplementary group membership is going to be a lot of what
determines whether files in ``/projects`` (designated for
collaborations) are accessible.

That's where this whole project founders.  ``setgroups()`` exists, but
it is a POSIX interface, and applies process-wide: that is, if any
thread calls ``setgroups()`` the resulting change is applied to all
threads in the process.  Nginx is a multithreaded web server.  What we
really wanted was a process-forking model.

This could have been worked around, perhaps: if we'd gone into the
``setgroups()`` implementation, we might have been able to figure out
which (undocumented) system calls are being used to do the actual
manipulation, steal those, and then just **not** signal the other
threads within the process; that, probably, would have ended up being a
new kernel module, which is not a maintenance headache we need, and
would necessarily have resulted in injecting ourselves far below the
layer we want to care about.  SQuaRE wants to be a consumer of a
Kubernetes service someone else provides; we explicitly don't care
what's running in the kernel, as long as we have the capabilities we
require.

Maybe we could have called ``setfsgid()`` in a loop for each group in
the user's groups, retrying the operation until it succeeded or we ran
out of groups, but that would have been a painful performance nightmare.

Apache
------

Apache was the original force behind WebDAV and the Apache web server
has pretty good support for it.  And since Apache largely predates
threads working very well, it does support a multiprocess model.  So it
might well have been possible to devise some model that would grab a new
process from the process pool, and make the appropriate system calls to
change the ownership of the process before letting it do work on the
user's behalf.

However, none of us were familiar with Apache modules at anything like
the level of detail that would have been required to even know if this
was feasible, much less implementing an impersonating Apache WebDAV
module.

Nublado
-------

This brings us to the approach we chose.  Abstractly, a lightweight
WebDAV server, running as a particular user, with all of that user's
permissions, is the correct approach.

As it happens, our `JupyterLab Controller
<https://github.com/lsst-sqre/jupyterlab-controller>`__ (AKA
``nublado``) provides the second half of this.  What it does is to spin
up a Kubernetes Pod, running as a particular user, which then runs
JupyterLab so the user can work on their own files, and on files shared
to them through POSIX groups.

The new Controller is actually decoupled rather nicely from JupyterHub:
the Hub Spawner interface has been reduced to a series of simple REST
calls, and all the impersonation pieces are handled by a combination of
Gafaelfawr arbitrating user access and providing delegated tokens as
necessary, and baking the resulting userids and groupids into the
containers the Controller is spawning.

That reduces the problem to writing a simple WebDAV server that we can
assume is already running as the correct user with the correct groups,
and then plumbing various routes to create, destroy, and interrogate
these servers into the JupyterLab Controller.

Since the pieces largely already existed, this was obviously the
least-effort route.

Implementation
==============

Containers, at their heart, are just fenced-off processes with their own
namespaces for PIDs, file systems, network routing, et cetera.  Clearly
what we wanted was the minimal container that would support serving
files when supplied with a user context.

The Go language turns out to be just about ideal for this.  Go does
static (or nearly-so) linking.  It also has a perfectly serviceable
`WebDAV server implementation
<https://pkg.go.dev/golang.org/x/net/webdav>`__ in its standard library.
Two minutes of Googling yielded this simple `WebDAV-enabled HTTP server
<https://gist.github.com/staaldraad/d835126cd46969330a8fdadba62b9b69>`__
which the author was kind enough to allow us to reuse under an MIT
license.

The resulting code is known as `Worblehat
<https://github.com/lsst-sqre/worblehat.git>`__ and adds a few settings
we can tweak, as well as an inactivity timeout shutdown.  It is packaged
as a single-file container: the only thing in it is the Worblehat
executable.  This presents a minimal attack surface.

That was the easy part.

The slightly harder part was implementing the machinery in the
JupyterLab Controller to automatically create and tear down the
resources to make and remove user fileservers on demand.  Even this
wasn't very tough; most of the effort was spent extending the Kubernetes
mock API for testing, which then gives us a more complete Kubernetes
mock going forward.

The final missing piece is a set of changes to Phalanx to add the new
routes and add ClusterRole capabilities for it to be able to manipulate
the objects that Labs don't use but Fileservers do.

.. Make in-text citations with: :cite:`bibkey`.
.. Uncomment to use citations
.. .. rubric:: References
..
.. .. bibliography:: local.bib lsstbib/books.bib lsstbib/lsst.bib
   lsstbib/lsst-dm.bib lsstbib/refs.bib lsstbib/refs_ads.bib
..  :style: lsst_aa
