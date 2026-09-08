#!/bin/bash
# Run an experiment on the second machine without taking it down.
#
# This lives in the repository because the incident it prevents is a repository fact.
# On 2026-09-08 a submission build on that box drove the load average to 167 with no
# memory left. It serves production for five other projects: a plain HTTP redirect took
# 9.3 seconds and one site stopped answering. Killing the job restored everything within
# a minute.
#
# Two caps, and the first attempt at each was wrong in a way worth recording:
#
#   memory   `ulimit -v` limits the virtual address space, which polars and xgboost
#            reserve far more of than they touch; a 6 GB cap aborted the job before it
#            read a row. A cgroup limits what is actually resident, which is the thing
#            that ran the machine out.
#
#   cpu      With memory capped alone the load average still sat above 20, because the
#            job takes all eight cores and leaves none for the services. Half the machine
#            is enough for an experiment.
#
# Deploy with: scp scripts/hetzner_guard.sh hetzner:~/prc-taxiout/guard.sh
# Use with:    ~/prc-taxiout/guard.sh python -u experiment.py
exec systemd-run --user --scope -q \
  -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=400% "$@"
