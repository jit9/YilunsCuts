"""This script defines the project input and output structure.

List of output files:

- {output_dir}
  - pickle results
- {output_dir}/pathologies/
  - cut thresholds overview plots
  - killedbyplot

- {output_dir}/pathologies/hist
  - histogram plot for each pathological parameters

- {output_dir}/pathologies/array
  - array plots for each pathological parameters
  - {output_dir}/pathologies/array/mean
    - plots of the mean of each parameter
  - {output_dir}/pathologies/array/std
    - plots of the std of each parameter

- {output_dir}/pathologies/season
  - each pathological parameters as a time series
  - {output_dir}/pathologies/season/mean
    - plots of the mean of each parameter
  - {output_dir}/pathologies/season/std
    - plots of the std of each parameter

- {output_dir}/flatfield/
  - flatfield array plot

- {output_dir}/calibration/
  - uranus calibration plot
  - {output_dir}/calibration/array
    - calibration array plot per tod
  - {output_dir}/calibration/resp
    - responsivity array plot per tod
  - {output_dir}/calibration/peak
    - planet amplitude plot per tod
  - {output_dir}/calibration/gain_inv
    - gain^inv plot per tod
"""

from .util import mkdir, parse_tag, parse_depot, tag_to_afsv
from dotmap import DotMap
import os.path as op

output_dir = "output"

def init(cutparam, output_dir=None):
    """initialize the project file structure.
    Args:
        cutparam (str): path to the cutparam file
        output_dir (str): output path for the pipeline
                          default to None
    """
    # define folder structures
    tag = parse_tag(cutparam)
    depot = parse_depot(cutparam)
    if not output_dir:
        output_dir = depot + '/Postprocess'
    root = mkdir(output_dir+'/'+tag)
    ff = mkdir(root+'/flatfield')
    cal = DotMap()
    cal.root = mkdir(root+'/calibration')
    cal.array = mkdir(cal.root+'/array')
    cal.resp = mkdir(cal.root+'/resp')
    cal.peak = mkdir(cal.root+'/peak')
    cal.gain_inv = mkdir(cal.root+'/gain_inv')
    patho = DotMap()
    patho.root = mkdir(root+'/pathologies')
    patho.hist = mkdir(root+'/pathologies/hist')
    patho.viz = mkdir(root+'/pathologies/viz')
    patho.season = DotMap()
    patho.season.root = mkdir(root+'/pathologies/season')
    patho.season.mean = mkdir(root+'/pathologies/season/mean')
    patho.season.median = mkdir(root+'/pathologies/season/median')
    patho.season.std  = mkdir(root+'/pathologies/season/std')
    patho.array = DotMap()
    patho.array.root = mkdir(root+'/pathologies/array')
    patho.array.mean = mkdir(root+'/pathologies/array/mean')
    patho.array.median = mkdir(root+'/pathologies/array/median')
    patho.array.std  = mkdir(root+'/pathologies/array/std')
    # consolidate all output information
    o = DotMap()
    o.root = root
    o.ff = ff
    o.cal = cal
    o.patho = patho
    o.pickle_file = op.join(o.root, tag + "_results.pickle")
    # consolidate all input information
    i = DotMap()
    i.root = op.dirname(cutparam)
    i.cutparam = cutparam
    i.cutParam = cutparam.replace("param","Param")
    i.ff = op.join(i.root, "ff_" + tag + ".dict")
    i.ar, i.freq, i.season, i.version = tag_to_afsv(tag)
    i.pickle_file = o.pickle_file
    i.run_dir = op.join(i.root, "run_" + i.version)
    i.db = op.join(i.run_dir, tag + ".db")
    # export for reporting
    e = DotMap()
    e.root = mkdir(root+'/report')
    # consolidate all information
    p = DotMap()
    p.i, p.o = i, o
    p.e = e
    p.tag = tag
    p.depot = depot
    return p
