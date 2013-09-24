.. Copyright © 2013 K Richard Pixley <rich@noir.com>

#########
CHANGELOG
#########

v0.8
    - refactored code in order to work within file descriptor and
      memory limits.
    - profiling to chase down gross inefficiencies, (like tarfile's
      pathological use of .tgz fles).
    - bzip2 and xz, (lzma), file support, (requires xz-utils library,
      liblzma-dev in debian)

v0.7
    - replace most tests
    - add command line wrapper
    - rework doc

v0.006
    - as open sourced by HP's osrb, sans tests
