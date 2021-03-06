from moby2.util import MobyDict
import sys, os, time
import argparse


def submit(cutparam):
    # load base parameters
    par = MobyDict.from_file(cutparam)

    # runtime parameters
    tpn = par.get("tpn", 20)  # task per node
    nnode = par.get("nnode", 1)
    jobname = par.get("jobname", "update_crit")
    nproc = tpn * nnode

    # output parameters
    basedir = os.path.dirname(os.path.abspath(cutparam))
    outdir = os.path.join(basedir, par["outdir"])
    runtime = par.get("runtime")
    qos = par.get("qos")
    nomp = par.get("nomp")
    # partition = par.get("partition", "serial")

    # find list of tods to process
    if not(os.path.isdir(outdir)): os.makedirs(outdir)

    # submit one slurm job on each node, so loop over node here
    for n in range(nnode):
        f = open( '%s/submitjob.sh.%d' % (outdir, n), 'w' )
        f.write( '#!/bin/sh\n' )
        f.write( '#SBATCH -N 1\n')
        f.write( '#SBATCH --ntasks-per-node=32\n')  # for della
        f.write( '#SBATCH -J %s%d\n' % (jobname,n))
        f.write( '#SBATCH -t %s\n' % runtime )
        f.write( '#SBATCH --qos %s\n' % qos )
        # f.write( '#SBATCH --partition %s\n' % partition)
        f.write( '#SBATCH --output=%s/slurmjob.log.%d\n' % (outdir, n))
        f.write( 'module load gcc\n' )
        f.write( 'module load openmpi\n' )
        f.write( 'source activate myenv\n' )  #FIXME
        f.write( 'cd %s\n' % basedir)
        start, end = n*tpn, (n+1)*tpn
        for i in range(start, end):
            f.write('OMP_NUM_THREADS=%d update_crit -n %d --index %d -f %s & sleep 1\n' % (nomp, nproc, i, cutparam))
        f.write('wait\n')
        f.close()
        os.system("sbatch %s/submitjob.sh.%d\n" % (outdir, n))
