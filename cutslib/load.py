"""convenient functions to load tods"""

import moby2
from .environ import CUTS_DEPOT
from .pathologies import Pathologies, get_pathologies
from .pathologies_tools import get_pwv


def load_tod(todname, tag=None, planet=None, partial=None):
    tod = moby2.scripting.get_tod({'filename': todname, 'repair_pointing':True})
    print("tod loaded")
    # load metadata with tag
    if tag:
        # try to load cuts
        try:
            cuts = moby2.scripting.get_cuts({
                'depot': CUTS_DEPOT,
                'tag': tag
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