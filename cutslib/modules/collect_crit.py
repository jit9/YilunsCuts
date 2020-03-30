"""This is a wrapper to the collectSeasonCrit script in moby2. It is
wrapped in this framework for convenience"""
import os
import moby2
import pickle, numpy as np, sys, os
from moby2.util.database import TODList
from cutslib.pathologies_tools import fix_tod_length, get_pwv
from cutslib.pathologies import Pathologies

class Module:
    def __init__(self, config):
        self.limit = config.getint("limit", None)

    def run(self, p):
        limit = self.limit

        # read parameters
        params = moby2.util.MobyDict.from_file(p.i.cutparam)
        depot = moby2.util.Depot(params.get('depot'))
        cutParams = moby2.util.MobyDict.from_file(p.i.cutParam)
        pathop = cutParams['pathologyParams']

        # get tod list
        obsnames = TODList.from_file(params.get("source_scans"))
        depot_file = p.i.db
        if os.path.isfile(depot_file):
            done = TODList.from_file(depot_file)
            undone = obsnames - done
            obsnames -= undone

        print("Collecting Criteria for %d files"%len(obsnames))
        tods = []
        sel = []
        psel = []
        scanf = []
        resp = []
        respSel = []
        cal = []
        ctimes = []
        criteria = {}
        alt = []
        if params.get("keys") is None:
            keys = ["corrLive", "DELive", "MFELive",
                    "rmsLive", "skewLive", "kurtLive",
                    "normLive", "gainLive", "jumpLive"]
        else:
            keys = params.get("keys")

        if limit:
            obsnames = obsnames[:limit]

        n = 0
        N = len(obsnames)
        for obs in obsnames:
            print("Collecting %s: %d out of %d"%(obs.split("/")[-1], n, N))
            n += 1
            try:
                tod = moby2.scripting.get_tod({"filename":obs, "read_data":False})
            except:
                print("Failed")
                continue
            if os.path.isfile(depot.get_full_path(Pathologies, tod=tod, tag=params['tag_patho'])) and \
               os.path.isfile(depot.get_full_path(moby2.TODCuts, tod=tod, tag=params["tag_out"])) and \
               os.path.isfile(depot.get_full_path(moby2.Calibration, tod=tod, tag=params["tag_cal"])):
                calo = depot.read_object(moby2.Calibration, tod=tod, tag=params["tag_cal"])
                if len(calo.cal)==0:
                    print("No calibration available")
                    continue
                pa = depot.read_object(Pathologies, tod=tod, tag=params['tag_patho'],
                                       options = {"tod":tod, "params":pathop},
                                       structure = params.get("structure"))
                for crit in keys:
                    if "values" in pa.crit[crit]:
                        criteria.setdefault(crit,[]).append( pa.crit[crit]["values"] )
                fix_tod_length(tod, pa.offsets)
                cuts = depot.read_object(moby2.TODCuts, tod=tod, tag=params["tag_out"])
                re, ff, _, re_sel, _, stable = pa.getpWCalibration()
                # get final cut
                lsel = np.zeros(pa.ndet)
                lsel[cuts.get_uncut()] = True
                sel.append(lsel)
                # get preselection
                presel = pa.preLiveSel
                psel.append(presel)
                # get other tod info
                tods.append(tod.info.name)
                scanf.append(pa.scan_freq)
                resp.append(re)
                respSel.append(re_sel)
                cal.append(calo.get_property("cal", det_uid=tod.det_uid, default=1)[1])
                ctimes.append(tod.info.ctime)
                alt.append(np.mean(tod.alt))

        data = {}
        data['name'] = tods
        data['sel'] = np.array(sel).T
        data['psel'] = np.array(psel).T
        data["live"] = pa.liveCandidates
        data["dark"] = pa.origDark
        data["scan_freq"] = scanf
        data["resp"] = np.array(resp).T
        data["respSel"] = np.array(respSel).T
        data["ff"] = ff
        data["cal"] = np.array(cal).T
        data["stable"] = stable
        data["ctime"] = np.array(ctimes)
        data["pwv"] = get_pwv(data["ctime"])
        data["alt"] = alt
        for k in list(criteria.keys()):
            data[k] = np.array(criteria[k]).T
        outfile = p.o.pickle_file
        print("Saving data: %s" % outfile)
        f = open(outfile, 'wb')
        p = pickle.Pickler(f,2)
        p.dump(data)
        f.close()
