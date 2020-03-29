"""This is a final processing module to generate the todinfo.txt file
that's required by mapmaker script

"""

import json, os.path as op, json, os
from cutslib.util import tag_to_afsv, to_scode, to_pa


class Module:
    def __init__(self, config):
        self.cut_release = config.get("cut_release", None)
        self.od_cmb = config.get("obs_details_cmb").split()
        self.od_noncmb = config.get("obs_details_noncmb").split()
        self.outfile = config.get("outfile", "todinfo.txt")

    def run(self, p):
        cr = self.cut_release
        od_cmb = self.od_cmb
        od_noncmb = self.od_noncmb
        outfile = self.outfile
        # load cut release
        cr_file = p.depot.get_deep((f'release_{cr}.txt',))
        with open(cr_file, "r") as f:
            release = json.loads(f.read())
        # load tags
        tags = list(release['tags'].keys())
        # write cmb fields
        cmb_entries = []
        for field in od_cmb:
            for tag in tags:
                # get tod list corresponding to the field and tag
                name = p.depot.get_deep(('SelectedTODs',
                                         release['tags'][tag]['tag_out'],
                                         f'selectedTODs_{field}.txt'))
                # parse afsv
                ar, freq, season, _ = tag_to_afsv(tag)
                # adjust formatting
                ar = to_pa(ar)
                season = to_scode(season)
                name = '{p}/'+'/'.join(name.split('/')[-2:])
                # create entry line
                entry = f"{name}\t{season} {ar} :f{freq:03d} cmb {field}"
                cmb_entries.append(entry)
        # write noncmb fields
        noncmb_entries = []
        for field in od_noncmb:
            for tag in tags:
                # get tod list corresponding to the field and tag
                name = p.depot.get_deep(('SelectedTODs',
                                         release['tags'][tag]['tag_out'],
                                         f'selectedTODs_{field}.txt'))
                # parse afsv
                ar, freq, season, _ = tag_to_afsv(tag)
                # adjust formatting
                ar = to_pa(ar)
                season = to_scode(season)
                name = '{p}/'+'/'.join(name.split('/')[-2:])
                # create entry line
                entry = f"{name}\t{season} {ar} :f{freq:03d} {field}"
                noncmb_entries.append(entry)
        # writing output file
        # check output dir exists
        outdir = op.abspath(op.dirname(outfile))
        if not op.exists(outdir):
            os.makedirs(outdir)
            print("Creating: %s" % outdir)
        with open(outfile, "w") as f:
            # write down path
            f.write(f"p = {p.depot.get_deep(('SelectedTODs',))}\n")
            f.write('\n')
            for entry in cmb_entries:
                f.write(entry+'\n')
            f.write('\n')
            for entry in noncmb_entries:
                f.write(entry+'\n')
        print("Writing to: %s" % outfile)