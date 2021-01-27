"""convenient functions to load tods"""

import numpy as np

import moby2
from .depot import Depot
from .environ import CUTS_DEPOT
from .pathologies import Pathologies, get_pathologies
from .pathologies_tools import get_pwv


glitchp = {'nSig': 10., 'tGlitch' : 0.007, 'minSeparation': 30, \
           'maxGlitch': 50000, 'highPassFc': 6.0, 'buffer': 200 }

def load_tod(todname, tag=None, planet=None, partial=None,
             release=None, rd=True, fs=True, fcode=None, **kwargs):
    if ':' in todname: todname, fcode = todname.split(':')
    opts = {'filename': todname, 'repair_pointing':True, 'read_data': rd, 'fix_sign': fs}
    opts.update(kwargs)
    tod = moby2.scripting.get_tod(opts)
    print("tod loaded")
    # load metadata with release tag
    if release:
        import yaml
        depot = Depot()
        release_file = depot.get_deep((f'release_{release}', 'release.txt'))
        with open(release_file, "r") as f:
            rl = yaml.load(f.read())
        print(f"Loaded tags from {release_file}")
        pa = tod.info.array.replace('ar','pa')
        scode = tod.info.season.replace('20','s')
        if tag: fcode = tag.split('_')[1]
        if not fcode: raise ValueError("Missing fcode")
        key = f"{pa}_{fcode}_{scode}_c11"
        tags = rl['tags'][key]
        # try to load cuts
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': tags['tag_out'],
            }, tod=tod)
            tod.cuts = cuts
            print(f"-> cuts loaded in tod.cuts tagged: {tags['tag_out']}")
        except:
            print("-> Warning: cuts not loaded successfully")
        # load planet cuts
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': tags['tag_planet']
            }, tod=tod)
            tod.planet = cuts
            print(f"-> planet cuts loaded in tod.planet tagged: {tags['tag_planet']}")
        except:
            print("-> Warning: planet cuts not loaded successfully")
        # load planet cuts
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': tags['tag_partial']
            }, tod=tod)
            tod.partial = cuts
            print(f"-> partial cuts loaded in tod.partial tagged: {tags['tag_partial']}")
        except:
            print("Warning: partial cuts not loaded successfully")
        # load calibrations
        try:
            depot = moby2.util.Depot(CUTS_DEPOT)
            cal = depot.read_object(moby2.Calibration, tod=tod, tag=tags['tag_cal'])
            tod.cal = cal
            print(f"-> cal loaded in tod.cal tagged: {tags['tag_cal']}")
        except:
            print("Warning: calibrations not loaded successfully")
        # load pathologies
        try:
            patho = get_pathologies({
                'depot': CUTS_DEPOT,
                'tag': tags['tag_out']
            }, tod=tod)
            tod.patho = patho
            print(f"-> patho loaded in tod.patho tagged: {tags['tag_out']}")
        except:
            print("Warning: patho not loaded successfully")
        # get pwv
        try:
            pwv = get_pwv([tod.ctime[0]])
            tod.pwv = pwv[0]
            print("-> pwv loaded in tod.pwv")
        except:
            print("Warning: pwv not loaded successfully")
    elif tag:
        # try to load cuts
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': tag,
            }, tod=tod)
            tod.cuts = cuts
            print("-> cuts loaded in tod.cuts")
        except:
            print("-> Warning: cuts not loaded successfully")
        # load planet cuts
        if not planet: planet = tag+'_planet'
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': planet
            }, tod=tod)
            tod.planet = cuts
            print("-> planet cuts loaded in tod.planet")
        except:
            print("-> Warning: planet cuts not loaded successfully")
        # load planet cuts
        if not partial: partial = tag+'_partial'
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': partial
            }, tod=tod)
            tod.partial = cuts
            print("-> partial cuts loaded in tod.partial")
        except:
            print("Warning: partial cuts not loaded successfully")
        # load calibrations
        try:
            depot = moby2.util.Depot(CUTS_DEPOT)
            cal = depot.read_object(moby2.Calibration, tod=tod, tag=tag)
            tod.cal = cal
            print("-> cal loaded in tod.cal")
        except:
            print("Warning: calibrations not loaded successfully")
        # load pathologies
        try:
            patho = get_pathologies({
                'depot': CUTS_DEPOT,
                'tag': tag
            }, tod=tod)
            tod.patho = patho
            print("-> patho loaded in tod.patho")
        except:
            print("Warning: patho not loaded successfully")
        # get pwv
        try:
            pwv = get_pwv([tod.ctime[0]])
            tod.pwv = pwv[0]
            print("-> pwv loaded in tod.pwv")
        except:
            print("Warning: pwv not loaded successfully")
    return tod

def get_tes(tod):
    """return tes dets mask"""
    return tod.info.array_data['det_type'] == 'tes'

def quick_transform(tod, steps=[], safe=False, glitchp=glitchp):
    """Short-hand notation for some common processings. Steps specified
    will be executed in order. Here are some possible steps:
      detrend: detrend tod for each det
      demean: remove the mean of the tod for each det
      demean_nospike: remove the mean with glitches masked
      cal: calibrate tod with tod.cal
      fill_cuts: fill cuts using tod.cuts
      ...
      more to add
    """
    for step in steps:
        if step == 'detrend':
            moby2.tod.detrend_tod(tod)
        elif step == 'demean':
            tod.data -= np.mean(tod.data, axis=1)[:,None]
        elif step == 'demean_nospike':
            if not hasattr(tod, 'cuts'):
                print(f"tod.cuts missing, skipping step: {step}")
                if not safe: continue
            demean_nospike(tod, tod.cuts)
        elif step == 'cal':
            if not hasattr(tod, 'cal'):
                print(f"tod.cal missing, skipping step: {step}")
                if not safe: continue
            tod.data[tod.cal.det_uid,:] *= tod.cal.cal[:,None]
        elif step == 'fill_cuts':
            if not hasattr(tod, 'cuts'):
                print(f"tod.cuts missing, skipping step: {step}")
                if not safe: continue
            moby2.tod.cuts.fill_cuts(tod, tod.cuts)
        elif step == 'ff_mce':  # find and fill mce cuts
            mce_cuts = moby2.tod.get_mce_cuts(tod)
            tod.mce_cuts = mce_cuts
            moby2.tod.fill_cuts(tod, mce_cuts, no_noise=True)
        elif step == 'ff_glitch':  # find and fill glitch cuts
            pcuts = moby2.tod.get_glitch_cuts(tod=tod, params=glitchp)
            moby2.tod.fill_cuts(tod, pcuts, no_noise=True)
            tod.pcuts = pcuts
        elif step == 'get_iv':
            cal = moby2.scripting.get_calibration({'type':'iv', 'source':'data'}, tod=tod)
            tod.cal = cal
        else:
            raise NotImplementedError

def demean_nospike(tod, cuts):
    """Remove the mean of tod without using the glitches"""
    mask = np.stack([c.get_mask() for c in cuts.cuts], axis=0)
    assert tod.nsamps >= cuts.nsamps
    data_masked = np.ma.masked_array(tod.data[:,:cuts.nsamps], mask)
    del mask
    mean = np.mean(data_masked, axis=1)
    del data_masked
    tod.data -= mean[:,None]
    del mean
    return tod
