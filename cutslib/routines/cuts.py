from __future__ import print_function
from __future__ import absolute_import
from past.builtins import basestring

import os, os.path as op
import numpy as np
import h5py

import moby2
from moby2.tod.cuts import TODCuts, CutsVector
from moby2.scripting import products
from moby2.analysis import hwp

from cutslib.todloop import Routine
from cutslib import pathologies, analysis as ana
from cutslib.tools import *


class CutMCE(Routine):
    def __init__(self, **params):
        """A routine that removes the MCE errors

        Args:
            no_noise (bool): whether to fill the cuts with noise
                             (default True)
        """
        Routine.__init__(self)
        self._no_noise = params.get('no_noise', True)

    def execute(self, store):
        # get tod
        tod = store.get("tod")
        # get mce cuts
        mce_cuts = moby2.tod.get_mce_cuts(tod)
        # fill the mce cuts
        moby2.tod.fill_cuts(tod, mce_cuts, no_noise=self._no_noise)
        # save the tod back to store
        store.set("tod", tod)


class CutSources(Routine):
    def __init__(self, **params):
        """A routine that cuts the point sources"""
        Routine.__init__(self)
        # retrieve other parameters
        self._tag_source = params.get('tag_source', None)
        self._source_list = params.get('source_list', None)
        self._no_noise = params.get('no_noise', True)
        self._pointing_par = params.get('pointing_par', None)
        self._mask_params = params.get('mask_params', {})
        self._shift_params = params.get('mask_shift_generator', None)
        self._depot_path = params.get('depot', None)
        self._write_depot = params.get('write_depot', False)
        self._hdf_cuts = params.get("hdf_source_cuts", None)
        self._force = params.get("force_source", False)

    def initialize(self):
        # get the depot
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))

        # check if source cut results exist
        sourceResult = os.path.exists(
            self._depot.get_full_path(
                moby2.TODCuts, tag=self._tag_source, tod=tod))
        # check if hdf source cuts are needed
        if self._hdf_cuts and not sourceResult:
            f = h5py.File(self._hdf_cuts, 'r', swmr=True)
            if tod.info.basename in f:
                grp = f[tod.info.basename]
                flags_sources = moby2.tod.TODFlags.from_hdf(grp)
                flags_sources_cuts = flags_sources.get_cuts('cut')
                # to avoid possible mismatch between det_uid in source cuts
                # versus the det_uid in the tod, we initialize an empty
                # cuts object for the tod (with the right det_uid) and merge
                # the sources cut in, to be safe.
                pos_cuts_sources = moby2.tod.TODCuts.for_tod(tod, assign=False)
                pos_cuts_sources.merge_tod_cuts(flags_sources_cuts, cut_missing=True)
                self._depot.write_object(pos_cuts_sources,
                                         tag=self._tag_source,
                                         force=True, tod=tod,
                                         make_dirs=True)
                sourceResult = True

        # if cuts exist, load it now
        if sourceResult and not self._force:
            self.logger.info("Loading time stream cuts (%s)" % self._tag_source)
            # load source cut
            source_cuts = self._depot.read_object(
                moby2.TODCuts, tag=self._tag_source, tod=tod)
            # fill the cuts in the TOD
            moby2.tod.fill_cuts(tod, source_cuts, no_noise=self._no_noise)

        # if source cut cannot be retrieved by tag_source, load it
        # through _source_list
        elif self._source_list is not None:
            self.logger.info("Finding new source cuts")

            # supply focal plane information to tod
            tod.fplane = products.get_focal_plane(self._pointing_par, tod.info)
            pointing_shift = (0,0)
            mask_params = self._mask_params
            shift_params = self._shift_params

            # check if shift is needed
            if shift_params is not None:
                pointing_shift = products.get_pointing_offset(
                    shift_params, tod=tod, source_offset=True)
            mask_params['offset'] = pointing_shift
            matched_sources = moby2.ephem.get_sources_in_tod(
                tod=tod, source_list=self._source_list, pointing_shift=pointing_shift)
            self.logger.info("matched sources: %s" % matched_sources)

            # create a placeholder cut object to store our source cuts
            pos_cuts_sources = moby2.TODCuts.for_tod(tod, assign=False)
            pos_cut_dict = {}

            # process source cut for each source
            for source in matched_sources:
                # compute the source cut associated with the source
                pos_cut_dict[source[0]] = moby2.tod.get_source_cuts(
                    tod, source[1], source[2], **mask_params)
                pos_cuts_sources.merge_tod_cuts(pos_cut_dict[source[0]])

            # write to depot, copied from moby2, not needed here
            if self._write_depot:
                self._depot.write_object(pos_cuts_sources,
                                         tag=self._tag_source,
                                         force=True, tod=tod, make_dirs=True)

            # fill the source cuts to the tod
            moby2.tod.fill_cuts(tod, pos_cuts_sources, no_noise=self._no_noise)

        # pass the processed tod back to data store
        store.set(self.outputs.get('tod'), tod)


class CutPlanets(Routine):
    def __init__(self, **params):
        """A routine that perform the planet cuts"""
        Routine.__init__(self)
        self._no_noise = params.get('no_noise', True)
        self._tag_planet = params.get('tag_planet', None)
        self._pointing_par = params.get('pointing_par', None)
        self._mask_params = params.get('mask_params', {})
        self._shift_params = params.get('mask_shift_generator', None)
        self._depot_path = params.get('depot', None)
        self._write_depot = params.get('write_depot', False)
        self._force_planet = params.get('force_planet', False)

    def initialize(self):
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        # get tod
        tod = store.get(self.inputs.get('tod'))

        # check if planetCuts exist
        planetResult = os.path.exists(
            self._depot.get_full_path(
                moby2.TODCuts, tag=self._tag_planet, tod=tod))

        # if planetCuts exist load it into variable pos_cuts_planets
        if planetResult and not self._force_planet:
            self.logger.info("Loading time stream cuts (%s)" % self._tag_planet)
            pos_cuts_planets = self._depot.read_object(
                moby2.TODCuts, tag=self._tag_planet, tod=tod)

        # if planetCuts do not exist generate it on the run
        else:
            self.logger.info("Finding new planet cuts")
            if not hasattr(tod, 'fplane'):
                tod.fplane = products.get_focal_plane(self._pointing_par,
                                                      tod.info)
            # load planet sources
            matched_sources = moby2.ephem.get_sources_in_patch(
                tod=tod, source_list=None)

            # check if shift is needed
            if self._shift_params is not None:
                # calculate pointing offset
                offset = products.get_pointing_offset(
                    self._shift_params, tod=tod, source_offset=True)

                # check if offset is calculated successfully, if not give
                # a zero offset
                if offset is None:
                    offset = (0., 0.)

                # calculate a map size
                if max(offset) > 20. / 60:
                    self._mask_params['map_size'] = max(offset) + 10. / 60
                self._mask_params['offset'] = offset

            self.logger.info("matched sources: %s" % matched_sources)

            # a place holder cut object to store all planet cut
            pos_cuts_planets = moby2.TODCuts.for_tod(tod, assign=False)
            pos_cut_dict = {}

            # process each planet source
            for source in matched_sources:
                # calculate planet cut
                pos_cut_dict[source[0]] = moby2.tod.get_source_cuts(
                    tod, source[1], source[2], **self._mask_params)
                # merge it into the total cut
                pos_cuts_planets.merge_tod_cuts(pos_cut_dict[source[0]])

            if self._write_depot:
            # write planet cut to depot, copied from moby2, not needed
            # here
                self._depot.write_object(pos_cuts_planets,
                                         tag=self._tag_planet, force=True, tod=tod,
                                         make_dirs=True)

        # fill planet cuts into tod
        moby2.tod.fill_cuts(tod, pos_cuts_planets, no_noise=self._no_noise)

        # pass the processed tod back to data store
        store.set(self.outputs.get('tod'), tod)


class FillCuts(Routine):
    def __init__(self, **params):
        """A routine that fill cuts from a given directory or a tag

        Parameters
        ----------
        cuts_dir: if cuts are stored in a given directory
        depot: one can also specify a depot while leaving cuts_dir empty
        tag: tag to load from depot
        no_noise: whether to fill cuts with noise
        """
        Routine.__init__(self)
        # retrieve other parameters
        self.cuts_dir = params.get('cuts_dir', None)
        self.depot = params.get('depot', None)
        self.tag = params.get('tag', None)
        self.no_noise = params.get('no_noise', True)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))

        # load cuts from a given directory
        if self.cuts_dir is not None:
            fname = self.get_name() + '.cuts'
            infile = op.join(self.cuts_dir, fname)
            mask_cuts = TODCuts.from_actpol_cuts_file(infile)
        # load from a given depot + tag
        elif self.depot is not None and self.tag is not None:
            mask_cuts = moby2.scripting.get_cuts({
                'depot': self.depot,
                'tag': self.tag
            }, tod=tod)
        self.logger.info("Filling in srcmask cuts")
        # fill the source cuts to the tod
        cuts = TODCuts.for_tod(tod, assign=False)
        cuts.merge_tod_cuts(mask_cuts)
        moby2.tod.fill_cuts(tod, cuts, no_noise=self.no_noise)
        # pass the processed tod back to data store
        store.set(self.outputs.get('tod'), tod)


class CutAz(Routine):
    def __init__(self, **params):
        """A routine that fill cuts from a given directory or a tag

        Parameters
        ----------
        cuts_dir: if cuts are stored in a given directory
        """
        Routine.__init__(self)
        self.tag = params.get('tag_az')
        self.depot = params.get('depot')

    def initialize(self):
        self.depot = moby2.util.Depot(self.depot)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))
        # analyze scan
        scan = ana.analyze_scan(tod)
        sflag = np.logical_or(scan['scan_flags'], scan['turn_flags'])
        cvec = CutsVector.from_mask(sflag).get_buffered(100)
        cuts = TODCuts.for_tod(tod, assign=False)
        # add az cuts for each det
        for d in tod.det_uid:
            cuts.add_cuts(d, cvec)
        # pass the processed tod back to data store
        store.set(self.outputs.get('azcut'), cuts)
        self.logger.info(f"Writing to depot: {self.tag}")
        self.depot.write_object(cuts, tag=self.tag, force=True, tod=tod,
                                make_dirs=True)


class RemoveSyncPickup(Routine):
    def __init__(self, **params):
        """This routine fit / removes synchronous pickup"""
        Routine.__init__(self)
        self._remove_sync = params.get('remove_sync', False)
        self._force_sync = params.get('force_sync', False)
        self._tag_sync = params.get('tag_sync', None)
        self._depot_path = params.get('depot', None)
        self._write_depot = params.get('write_depot', False)

    def initialize(self):
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))

        # Check for existing results, to set what operations must be
        # done/redone.
        sync_result = os.path.exists(
            self._depot.get_full_path(
                moby2.tod.Sync, tag=self._tag_sync, tod=tod))

        # determine if sync is needed
        skip_sync = not self._remove_sync or (not self._force_sync
                                              and sync_result)

        # obtain scan frequency
        scan_freq = moby2.tod.get_scan_info(tod).scan_freq

        if (self._remove_sync) and (scan_freq != 0):
            self.logger.info("Removing Sync")
            # check if sync can be skipped
            if skip_sync:
                self.logger.info("Using old sync")
                ss = self._depot.read_object(
                    moby2.tod.Sync, tag=self._tag_sync, tod=tod)
            # if not generate it on the go
            else:
                self.logger.info("Computing new sync")
                ss = moby2.tod.Sync(tod)
                ss.findOutliers()
                ss = ss.extend()

                # write sync object to disk
                if self._write_depot:
                    self._depot.write_object(ss, tag=self._tag_sync,
                                             tod=tod, make_dirs=True,
                                             force=True)

            ss.removeAll()
            del ss

        # pass the processed tod back to data store
        store.set(self.outputs.get('tod'), tod)


class CutPartial(Routine):
    def __init__(self, **params):
        """A routine that performs the partial cuts"""
        Routine.__init__(self)
        self._tag_partial = params.get('tag_partial', None)
        self._force_partial = params.get('force_partial', False)
        self._glitchp = params.get('glitchp', {})
        self._include_mce = params.get('include_mce', True)
        self._depot_path = params.get('depot', None)
        self._no_noise = params.get('no_noise', True)
        self._write_depot = params.get('write_depot', False)

    def initialize(self):
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))

        # check if partial results already exist
        partial_result = os.path.exists(
            self._depot.get_full_path(moby2.TODCuts,
                                      tag=self._tag_partial, tod=tod))
        # check if we need to skip creating partial cuts
        skip_partial = not self._force_partial and partial_result

        # if we want to skip creating partial cuts, load from depot
        if skip_partial:
            # Read existing result
            self.logger.info("Loading partial cuts (%s)" % self._tag_partial)
            cuts_partial = self._depot.read_object(
                moby2.TODCuts, tag=self._tag_partial, tod=tod)
        # otherwise generate partial cuts now
        else:
            self.logger.info('Generating partial cuts')

            # Generate and save new glitch cuts
            # note calbol may not be implemented...
            cuts_partial = moby2.tod.get_glitch_cuts(
                tod=tod, params=self._glitchp)

            # check if we want to include mce_cuts
            if self._include_mce:
                # find mce cuts
                mce_cuts = moby2.tod.get_mce_cuts(tod)

                # merge it with the partial cuts
                cuts_partial.merge_tod_cuts(mce_cuts)

            # write to depot, not needed here
            if self._write_depot:
                self._depot.write_object(cuts_partial,
                                         tag=self._tag_partial,
                                         tod=tod, make_dirs=True, force=True)

        # fill the partial cuts in our tod
        moby2.tod.fill_cuts(
            tod, cuts_partial, extrapolate=False, no_noise=self._no_noise)

        # save the partial cuts in tod object for further processing
        tod.cuts = cuts_partial

        # pass the tod back to the store
        store.set(self.outputs.get('tod'), tod)


class SubstractHWP(Routine):
    def __init__(self, input_key, output_key, **params):
        """This routine substracts the A(chi) signal from HWP"""
        Routine.__init__(self)
        self._input_key = params.get('input_key', None)
        self._output_key = params.get('output_key', None)
        self._hwp_par = params.get('hwp_par')
        self._depot_path = params.get('depot', None)

    def initialize(self):
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        # retrieve tod
        tod = store.get(self.inputs.get('tod'))

        self.logger.info("Substract HWP signal")

        # retrieve hwp_modes object from depot
        hwp_modes = self._depot.read_object(
            hwp.HWPModes,
            tag=self._hwp_par['a_chi']['tag'],
            tod=tod,
            structure=self._hwp_par['a_chi']['structure'])

        # get hwp angles
        hwp_angles = moby2.scripting.products.get_hwp_angles(
            self._hwp_par['angles'], tod)

        # substracting the hwp sinal
        r = hwp_modes.get_reconstructor(hwp_angles * np.pi / 180)
        hwp_signal = r.get_achi()
        tod.data[hwp_modes.det_uid, :] -= hwp_signal

        # pass the tod to the data store
        store.set(self.outputs.get('tod'), tod)


class FindJumps(Routine):
    def __init__(self, **params):
        Routine.__init__(self)
        self._dsStep = params.get('dsStep', None)
        self._window = params.get('window', None)

    def execute(self, store):
        tod = store.get(self.inputs.get('tod'))

        # find jumps
        jumps = moby2.libactpol.find_jumps(tod.data,
                                           self._dsStep,
                                           self._window)
        # store the jumps values
        crit = {
            'jumpLive': jumps,
            'jumpDark': jumps,
        }

        # save to data store
        store.set(self.outputs.get('jumps'), crit)


class FindPathologies(Routine):
    def __init__(self, **params):
        Routine.__init__(self)
        self._depot_path = params.get('depot', None)
        self._tag_patho = params.get('tag_patho', None)
        self._force_patho = params.get('force_patho', False)
        self._pathop = params.get('pathop', {})

    def initialize(self):
        # get the depot
        self._depot = moby2.util.Depot(self._depot_path)

    def execute(self, store):
        tod = store.get("tod")
        pathoResult = os.path.exists(
            self._depot.get_full_path(pathologies.Pathologies,
                                      tag=self._tag_patho, tod=tod))
        skip_patho = (not self._force_patho) and pathoResult

        if skip_patho:
            self.logger.info("Using old pathologies result")

        else:
            self.logger.info("Finding new pathologies")
            pa = pathologies.Pathologies(tod, self._pathop,
                                         noExclude=True)
            err = pa.findPathologies()
            self.logger.info("err = %d" % err)
            if err == 0:
                self._depot.write_object(pa, tag=self._tag_patho,
                                         force=True, tod=tod, make_dirs=True)
