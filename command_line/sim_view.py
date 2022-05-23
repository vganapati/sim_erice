from __future__ import absolute_import, division, print_function
"""
Plot the PNG files
Derek Mendez, dermen@lbl.gov

Generate and load simulated images on the fly
Iris Young, idyoung@lbl.gov
# LIBTBX_SET_DISPATCHER_NAME simtbx.sim_view
"""
try:  # py2/3 compat 
    import Tkinter as tk
except ImportError:
    import tkinter as tk

import numpy as np
import matplotlib as mpl
mpl.use('TkAgg')
import pylab as plt
import os, math

from matplotlib.backends.backend_tkagg import \
    FigureCanvasTkAgg, NavigationToolbar2Tk

import libtbx.load_env
from sim_erice.on_the_fly_simdata import run_simdata, get_SIM, randomize_orientation
from simtbx.nanoBragg.tst_nanoBragg_multipanel import beam, whole_det
from simtbx.diffBragg import hopper_utils
from LS49.spectra.generate_spectra import spectra_simulation
from iotbx.crystal_symmetry_from_any import extract_from as extract_symmetry_from
from iotbx.pdb.fetch import get_pdb
from cctbx.uctbx import unit_cell
from dxtbx_model_ext import Crystal
from scitbx import matrix
from scitbx.math import gaussian
from dials.array_family import flex
from libtbx import easy_pickle
from random import randint
import time

help_message="""SimView: lightweight simulator and viewer for diffraction still images.

Run without any arguments, this program simulates diffraction of a small
lysozyme crystal. You may provide a different pdb file on the command line
instead, or may request the program fetch one from the PDB by supplying its PDB
ID and the -f flag (for "fetch"). If this fails you may want to try using the
command line program "iotbx.fetch_pdb" instead.

Diffraction from your crystal will be simulated with a set of default parameters
for mosaic block size, beam energy and bandpass, etc. that you can change by
adjusting each of the dials. Parameters to be adjusted can be selected either
with the drop-down menu or with keyboard shortcuts as follows:

Left arrow or p:    previous parameter
Right arrow or n:   next parameter
Up arrow:           increase this parameter
Down arrow:         decrease this parameter
Shift-up arrow:     increase this parameter a lot
Shift-down arrow:   decrease this parameter a lot
Space bar:          simulate a new stochastic XFEL pulse
R:                  reset all parameters to defaults
I:                  toggle between image display modes
S:                  toggle spectrum shape
O:                  randomize crystal orientation
U:                  update reference image (in red)

(Note that matplotlib binds the left arrow key to resetting the field of view,
so both this effect and selection of the previous parameter will take place
if you are zoomed in on an area. The right arrow key can restore the zoom.)

Explanation of parameters:

DomainSize: the small blocks within crystals that are internally perfectly
aligned and identical are called mosaic domains. The average size of a domain
is one contributing factor determining the sharpness of the Bragg peaks. As
the size of the mosaic domain increases, the effect of constructive
interference of the scattered X-rays gets stronger, and the peak sharpens.

MosAngDeg: the mosaic domains are misoriented relative to one another by an
average angle denoted the mosaic angle, displayed here in degrees. Larger
differences in the orientations of the domains produce contributions to
Bragg peaks over a wider area on the detector, resulting in more diffuse
spots.

a, b, c: the parameters of the crystal unit cell. Depending on the symmetry
of the crystal, these may all vary independently or may be constrained to
scale together, in which case not all unit cell lengths will be exposed as
adjustible dials. Larger unit cells produce constructive and destructive
interference at smaller angles, resulting in more closely spaced Bragg
peaks on the detector.

Missetting angles in degrees: differences between the true orientation of
the crystal and what is determined during indexing. A misorientation of
the X or Y axis means a misestimation of which spots are in diffracting
conditions, and will affect which spots (or how much of the spots) appear
on the detector. Since the Z axis is along the beam direction,
misorientation in Z results in rotation of the entire diffraction pattern.

Energy/Bandwidth: the energy of the X-ray beam denotes the average energy
of an individual pulse. For X-ray free electron laser (XFEL) pulses
generated by self-amplified spontaneous emission (SASE), each pulse is
spiky and stochastic, with a typical bandwidth of between 10 and 30 eV.
A monochromater may be used to narrow this to around 1 eV.

Spectrum shape: to simulate images with real SASE spectra, toggle this
option to "SASE". To display diffraction produced by a smooth Gaussian
function that can be adjusted in energy and bandwidth, toggle this to
"Gaussian". SASE spectra are stochastic and will intentionally not be
modified by the energy and bandwidth controls. The "monochromatic"
option is recommended when diffuse scattering is enabled, to offset the
greater computational cost.

Fhkl: when we observe diffraction from a single particle, we are seeing
the Fourier transform of the particle, with [a great deal of] added
noise. For many copies of a particle all in the same orientation, we can
expect the signal to be much stronger. If these aligned particles are
also periodically spaced, as in the context of a crystal, they act as a
diffraction grating, and we see this signal only at positions of
constructive interference (the reciprocal lattice points in diffracting
conditions, i.e. Bragg peaks). In order to better see the effects of the
above parameters, we can ignore the Fourier transform of the asymmetric
unit and pretend all of the Bragg peaks have uniform intensity. This is
what we are simulating when we display "SFs on/off".

Diffuse scattering: this physical effect is a result of variation and
imperfection within the crystal and surrounding solvent, and it appears
as X-ray scattering between and around the Bragg peaks. Modeling this
can be toggled on or off. It is recommended to use the monochromatic
spectrum setting when calculating diffuse signal.

Diff_gamma and diff_sigma: parameters describing the diffuse scattering
signal. TODO: write more here after reading up on what these mean.

Aniso: anisotropic quality to the diffuse scattering. This is arbitrarily
assigned directionality, and the adjustible parameter controls the
degree to which this effect is observed.

Further notes on the image viewer: a random orientation can be assigned
to the crystal by pressing the "Randomize orientation" button any number
of times. Both the simulated and reference image update in this event.
Outside of this situation, the reference image will be identical to your
starting default parameters and can be updated to current parameters by
pressing "Update reference". This can help highlight the difference
between selected combinations of parameters. Finally, the viewer has
three display modes, one in which the reference image is displayed in red
and the current simulation is displayed in blue (with perfect overlap
resulting in white or gray), and two in which only the simulated image
is visible, displayed in either color or grayscale. You can cycle between
these modes with the "Toggle image mode" button.
"""

class SimView(tk.Frame):

    def __init__(self, master, params, pdbfile, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)

        self.master = master
        self.params = params
        self.dial_names = list(self.params.keys())
        self.current_dial = self.dial_names[0]

        symmetry = extract_symmetry_from(pdbfile)
        sg = str(symmetry.space_group_info())
        ucell = symmetry.unit_cell()
        fmat = matrix.sqr(ucell.fractionalization_matrix())
        cryst = Crystal(fmat, sg)
        panel = whole_det[0]
        s0 = beam.get_unit_s0()
        fast = panel.get_fast_axis()
        slow = panel.get_slow_axis()
        offset_orig = (2, -24, -100.)
        panel.set_frame(fast, slow, offset_orig)
        self.SIM = get_SIM(whole_det, beam, cryst, pdbfile)
        self.SIM_noSF = get_SIM(whole_det, beam, cryst)
        self.xtal = self.SIM.crystal.dxtbx_crystal
        self.ucell = self.xtal.get_unit_cell().parameters()
        self.scaled_ucell = self.ucell
        self.sg = self.xtal.get_space_group()
        self._load_params_only()
        self.percentile = 99.9
        self.image_mode = "rgb"
        self.spectrum_shape = "Gaussian"
        self.SASE_sim = spectra_simulation()
        self.SASE_iter = self.SASE_sim.generate_recast_renormalized_images(
            nlimit=100, energy=self._VALUES["Energy"], total_flux=1e12)
        self._update_spectrum(new_pulse=True)
        self.diffuse_scattering = False

        fsize, ssize = whole_det[0].get_image_size()
        img_sh = 1,ssize, fsize
        self.pfs = hopper_utils.full_img_pfs(img_sh)
        self.fast = self.pfs[1::3].as_numpy_array()
        self.slow = self.pfs[2::3].as_numpy_array()
        self.pan = self.pfs[0::3].as_numpy_array()
        self.img_ref = np.zeros((1, ssize, fsize))
        self.img_sim = np.zeros((1, ssize, fsize))
        self.img_cmap = np.zeros((ssize, fsize))
        self.img_rgb = np.zeros((ssize, fsize, 3))
        self.start_ori = self.SIM.crystal.dxtbx_crystal.get_U()
        self._generate_image_data(update_ref=True)
        self.img_rgb[:,:,0] = self._normalize_image_data(self.img_ref[0])

        self._set_option_menu()
        self._make_master_label()

        self._init_fig()

        self._pack_canvas()
        self._reset()
        self._display(init=True)

        self.bind()

        # set the option menu first
        self.dial_choice.set(self.current_dial)


    def _pack_canvas(self):
        """ embed the mpl figure"""
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master) 
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP,fill=tk.BOTH,
            expand=tk.YES)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.master)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, 
            fill=tk.BOTH, expand=tk.YES)


    def _init_fig(self):
        """ initialize the mpl fig"""
        self.fig = plt.figure(1)
        self.ax = plt.Axes(self.fig, [0,0,1,1])
        self.fig.add_axes(self.ax)
        self.ax.set_axis_off()
        self.ax.set_aspect("equal")
        self.fig.set_size_inches([9.22, 3.8]) 

    def _set_option_menu(self):
        """create an option menu for selecting params"""
        self.dial_choice = tk.StringVar()
       
        _opt_frame = tk.Frame(self.master)
        _opt_frame.pack(side=tk.TOP, expand=tk.NO)
        _button_frame = tk.Frame(self.master)
        _button_frame.pack(side=tk.TOP, expand=tk.NO)
        
        tk.Label( _opt_frame, text="Adjusting variable: ", 
            font=("Helvetica",15), width=16)\
            .pack(side=tk.LEFT)

        self.param_opt_menu = tk.OptionMenu(_opt_frame, 
            self.dial_choice,
            *self.dial_names,
            command=self._update_dial)
        self.param_opt_menu.pack(side=tk.LEFT)
        self.param_opt_menu.config(width=10)
        self.param_opt_menu.config(font=("Helvetica", 15))

        r=tk.Button(_opt_frame, command=self._reset, text="Reset all")
        r.pack(side=tk.LEFT)
        r.config(font=("Helvetica", 15))
        r.config(width=8)

        i=tk.Button(_opt_frame, command=self._toggle_image_mode, text="Toggle image mode")
        i.pack(side=tk.LEFT)
        i.config(font=("Helvetica", 15))
        i.config(width=18)

        d=tk.Button(_button_frame, command=self._toggle_diffuse_scattering, text="Toggle diffuse scattering")
        d.pack(side=tk.LEFT)
        d.config(font=("Helvetica", 15))
        d.config(width=22)

        s=tk.Button(_button_frame, command=self._toggle_spectrum_shape, text="Toggle spectrum shape")
        s.pack(side=tk.LEFT)
        s.config(font=("Helvetica", 15))
        s.config(width=20)

        o=tk.Button(_button_frame, command=self._randomize_orientation, text="Randomize orientation")
        o.pack(side=tk.LEFT)
        o.config(font=("Helvetica", 15))
        o.config(width=20)

        u=tk.Button(_opt_frame, command=self._update_reference, text="Update reference image")
        u.pack(side=tk.LEFT)
        u.config(font=("Helvetica", 15))
        u.config(width=21)

    def _update_dial(self, new_dial):
        if new_dial != self.current_dial:
            self.current_dial = new_dial
            self.dial_choice.set(self.current_dial)
            self._display()

    def _load_params_only(self):
        """load params that can be adjusted"""
        self._VALUES = {}
        self._LABELS = {}
        # generate a,b,c based on unit cell for the loaded pdb
        params["a"] = [scale * self.ucell[0] for scale in params["ucell_scale"]]
        params["b"] = [scale * self.ucell[1] for scale in params["ucell_scale"]]
        params["c"] = [scale * self.ucell[2] for scale in params["ucell_scale"]]
        del params["ucell_scale"]
        # fill all defaults
        for dial, (_, _, _, _, default) in params.items():
            self._VALUES[dial] = default
            self._LABELS[dial] = self._get_new_label_part(dial, default)
        # dependent on crystal symmetry: test if axes can be independently adjusted
        a, b, c, al, be, ga = self.ucell
        test_c = (a, b, c+10, al, be, ga)
        test_b = (a, b+10, c, al, be, ga)
        test_abc = (a*1.5, b*1.5, c*1.5, al, be, ga)
        if not self.sg.is_compatible_unit_cell(unit_cell(test_c)):
            del self._VALUES["c"]
            del self._LABELS["c"]
        if not self.sg.is_compatible_unit_cell(unit_cell(test_b)):
            del self._VALUES["b"]
            del self._LABELS["b"]
        if not self.sg.is_compatible_unit_cell(unit_cell(test_abc)):
            del self._VALUES["a"]
            del self._LABELS["a"]
        # if a,b,c remaining: all vary independently
        # if a,b remaining: c scales with a
        # if a,c remaining: b scales with a
        # if b,c remaining: c scales with b
        # if a remaining: a,b,c all vary together
        self.dial_names = self._VALUES.keys()

    def _update_normalization(self):
        """update normalization"""
        exponent = self._VALUES["Brightness"]*2-2
        self.percentile = 100 - 10**exponent
        self.img_rgb[:,:,0] = self._normalize_image_data(self.img_ref) # red channel

    def _normalize_image_data(self, img_data):
        """scale data to [0,1] where variable %ile intensities and above are set to 1."""
        scale = 1./max(1e-50,np.percentile(img_data, self.percentile))
        scaled_data = img_data * scale
        scaled_data[scaled_data > 1] = 1
        return scaled_data

    def _generate_image_data(self, update_ref=False):
        """generate image to match requested params"""
        # t = time.time()
        SIM = self.SIM if self._VALUES["Fhkl"] else self.SIM_noSF
        diffuse_gamma = (
            self._VALUES["Diff_gamma"],
            self._VALUES["Diff_gamma"] * self._VALUES["Aniso"],
            self._VALUES["Diff_gamma"] / self._VALUES["Aniso"]
            ) if self.diffuse_scattering else None
        diffuse_sigma = (
            self._VALUES["Diff_sigma"],
            self._VALUES["Diff_sigma"] * self._VALUES["Aniso"],
            self._VALUES["Diff_sigma"] / self._VALUES["Aniso"]
            ) if self.diffuse_scattering else None
        pix = run_simdata(SIM, self.pfs, self.scaled_ucell,
            tuple([(x,x,x) for x in [self._VALUES["DomainSize"]]][0]),
            (self._VALUES["RotX"]*math.pi/180.,
            self._VALUES["RotY"]*math.pi/180.,
            self._VALUES["RotZ"]*math.pi/180.),
            spectrum=self.spectrum_Ang,
            eta_p=self._VALUES["MosAngDeg"],
            diffuse_gamma=diffuse_gamma,
            diffuse_sigma=diffuse_sigma)
        # t = time.time()-t
        self.img_sim[self.pan, self.slow, self.fast] = pix
        if update_ref:
            self.img_ref[self.pan, self.slow, self.fast] = pix
            self.img_rgb[:,:,0] = self._normalize_image_data(self.img_ref[0]) # red channel
        self.img_cmap = self._normalize_image_data(self.img_sim[0])
        self.img_rgb[:,:,1] = self._normalize_image_data(self.img_sim[0] + self.img_ref[0]) # green channel (grayscale if identical)
        self.img_rgb[:,:,2] = self._normalize_image_data(self.img_sim[0]) # blue channel

    def _toggle_diffuse_scattering(self, _press=None):
        self.diffuse_scattering = not self.diffuse_scattering
        self._generate_image_data()
        self._display()

    def _toggle_spectrum_shape(self, _press=None):
        options = ["Gaussian", "SASE", "monochromatic"]
        current = options.index(self.spectrum_shape)
        self.spectrum_shape = options[current-2]
        self._update_spectrum(new_pulse=True)
        self._generate_image_data()
        self._display()

    def _update_spectrum(self, new_pulse=False):
        if self.spectrum_shape == "Gaussian":
            bw = 0.01*self._VALUES["Bandwidth"]*self._VALUES["Energy"] # bandwidth in eV
            gfunc = gaussian.term(1, 4 * math.log(2)/(bw**2)) # FWHM of bw, mu == 0
            self.spectrum_eV = [(energy + self._VALUES["Energy"], 1e12 * gfunc.at_x(energy)) \
                                for energy in range(-50,51)]
            self.spectrum_Ang = [(12398./energy, flux) for (energy, flux) in self.spectrum_eV]
        elif self.spectrum_shape == "SASE":
            if new_pulse:
                self.pulse_energies_Ang, self.flux_list, self.avg_wavelength_Ang = next(self.SASE_iter)
            self.spectrum_Ang = list(zip(self.pulse_energies_Ang, self.flux_list))
        elif self.spectrum_shape == "monochromatic":
            self.spectrum_Ang = [(12398./self._VALUES["Energy"], 1e12)] # single wavelength for computational speed
        else:
            raise NotImplemented("Haven't implemented a spectrum of the requested shape {}".format(shape))

    def _update_ucell(self, dial, new_value):
        # scale one or more lengths depending on symmetry
        if dial == "a":
            a = new_value
            scale = new_value / self.ucell[0]
            b = self.scaled_ucell[1] if "b" in self.dial_names else scale * self.ucell[1]
            c = self.scaled_ucell[2] if "c" in self.dial_names else scale * self.ucell[2]
        elif dial == "b":
            a = self.scaled_ucell[0]
            b = new_value
            scale = new_value / self.ucell[1]
            c = self.scaled_ucell[2] if "c" in self.dial_names else scale * self.ucell[2]
        elif dial == "c":
            a = self.scaled_ucell[0]
            b = self.scaled_ucell[1]
            c = new_value
        self.scaled_ucell = (a,b,c,*self.ucell[3:6])

    def _randomize_orientation(self, _press=None):
        seed1 = randint(0,1024)
        seed2 = randint(0,1024)
        randomize_orientation(self.SIM, seed_rand=seed1, seed_mersenne=seed2)
        randomize_orientation(self.SIM_noSF, seed_rand=seed1, seed_mersenne=seed2)
        self._generate_image_data(update_ref=True)
        self._display()

    def _update_reference(self, _press=None):
        self._generate_image_data(update_ref=True)
        self._display()

    def _make_master_label(self):
        """label that will be updated for each image"""
        self.master_label = tk.Label(self.master, text=\
"""DomainSize: ____; MosAngleDeg: ____; ____; a,b,c = ____;
Missetting angles in degrees (X,Y,Z) = (____, ____}, ____);
Diffuse gamma: ____, sigma: ____, anisotropy factor: ____;
Energy/Bandwidth= ____ / ____; Spectra: ____; ____; Brightness: ____""", font="Helvetica 15", width=350)
        self.master_label.pack(side=tk.TOP, expand=tk.NO)

    def _update_label(self):
        self._label = """Domain size: {mosdom}; Mosaic angle: {mosang}; {sigma}; a,b,c = {ucell};
Missetting angles in degrees (X,Y,Z) = ({rotx}, {roty}, {rotz});
Diffuse gamma: {gamma}, sigma: {sigma}, anisotropy factor: {aniso};
Energy/Bandwidth = {energy}/{bw}; Spectra: {spectra}; {Fhkl}; Brightness: {bright}""".format(
            mosdom=self._LABELS["DomainSize"],
            mosang=self._LABELS["MosAngDeg"],
            gamma=self._LABELS["Diff_gamma"] if self.diffuse_scattering else "N/A",
            sigma=self._LABELS["Diff_sigma"] if self.diffuse_scattering else "N/A",
            aniso=self._LABELS["Aniso"] if self.diffuse_scattering else "N/A",
            ucell=self._LABELS["ucell"], # updated when any of a,b,c are updated
            energy=self._LABELS["Energy"] if self.spectrum_shape in ["Gaussian", "monochromatic"] else "N/A",
            bw=self._LABELS["Bandwidth"] if self.spectrum_shape == "Gaussian" else "N/A",
            spectra=self.spectrum_shape,
            rotx=self._LABELS["RotX"],
            roty=self._LABELS["RotY"],
            rotz=self._LABELS["RotZ"],
            Fhkl=self._LABELS["Fhkl"],
            bright=self._LABELS["Brightness"]
        )

    def _get_new_label_part(self, dial, new_value):
        if dial == "DomainSize":
            return "{v}x{v}x{v}".format(v=new_value)
        elif dial == "MosAngDeg":
            return "{:.2f}º".format(new_value)
        elif dial == "Diff_gamma":
            return "{}".format(new_value)
        elif dial == "Diff_sigma":
            return "{:.2f}".format(new_value)
        elif dial == "Aniso":
            return "{:.2f}".format(new_value)
        elif dial in ["a", "b", "c"]:
            a,b,c = self.scaled_ucell[:3]
            self._LABELS["ucell"] = "{a:.2f}, {b:.2f}, {c:.2f}".format(a=a, b=b, c=c)
            return None
        elif dial == "Energy":
            return "{:d}".format(new_value)
        elif dial == "Bandwidth":
            return "{:.2f}%".format(new_value)
        elif dial in ["RotX", "RotY", "RotZ"]:
            return "{:+.2f}".format(new_value)
        elif dial == "Fhkl":
            return "SFs {}".format("on" if new_value else "off")
        elif dial == "Brightness":
            return "{:.2f}".format(new_value)

    def _display(self, init=False):
        """display the current image"""
        if init:
            if self.image_mode == "rgb":
                self.aximg = self.ax.imshow(self.img_rgb)
            elif self.image_mode == "cmap":
                self.aximg = self.ax.imshow(self.img_cmap, cmap='magma')
            else:
                self.aximg = self.ax.imshow(self.img_cmap, cmap='Greys_r')
        else:
            if self.image_mode == "rgb":
                self.aximg.set_data(self.img_rgb)
            else:
                self.aximg.set_data(self.img_cmap)

        self._update_label()
        self.master_label.config(text=self._label)
        self.master_label.config(font=("Courier", 15))

        self.canvas.draw()

    def _toggle_image_mode(self, _press=None):
        options = ["rgb", "cmap", "greyscale"]
        current = options.index(self.image_mode)
        self.image_mode = options[current-2]
        self._display(init=True)

    def bind(self):
        """key bindings"""
        self.master.bind_all("<Up>", self._small_step_up)  # increase this parameter
        self.master.bind_all("<Shift-Up>", self._big_step_up) # increase this parameter a lot
        self.master.bind_all("<R>", self._reset)  # reset all params to default settings
        self.master.bind_all("<Down>", self._small_step_down)  # decrease this parameter
        self.master.bind_all("<Shift-Down>", self._big_step_down) # decrease this parameter a lot
        self.master.bind_all("<space>", self._new_pulse) # repeat the simulation with a new spectrum
        
        self.master.bind_all("<Left>", self._prev_dial)
        self.master.bind_all("<p>", self._prev_dial)
        self.master.bind_all("<Right>", self._next_dial)
        self.master.bind_all("<n>", self._next_dial)

        self.master.bind_all("<I>", self._toggle_image_mode) # toggle between RGB and colormap views
        self.master.bind_all("<D>", self._toggle_diffuse_scattering) # toggle diffuses scattering on/off
        self.master.bind_all("<S>", self._toggle_spectrum_shape) # toggle between Gaussian, SASE and mono beam
        self.master.bind_all("<O>", self._randomize_orientation) # randomize crystal orientation
        self.master.bind_all("<U>", self._update_reference) # update reference image (in red)

    def _next_dial(self, tkevent):
        try:
            new_dial = self.dial_names[self.dial_names.index(self.current_dial) + 1]
            self._update_dial(new_dial)
        except IndexError:
            pass

    def _prev_dial(self, tkevent):
        try:
            new_dial = self.dial_names[self.dial_names.index(self.current_dial) - 1]
            self._update_dial(new_dial)
        except IndexError:
            pass

    def _new_pulse(self, tkevent):
        self._update_spectrum(new_pulse=True)
        self._generate_image_data()
        self._display()

    def _set_new_value(self, dial, new_value):
        self._VALUES[dial] = new_value
        if dial in ["Energy", "Bandwidth"]:
            self._update_spectrum()
        elif dial in ["a", "b", "c"]:
            self._update_ucell(dial, new_value)
        elif dial == "Brightness":
            self._update_normalization()
        # updating labels must happen after updating values for ucell
        self._LABELS[dial] = self._get_new_label_part(dial, new_value)
        self._generate_image_data()
        self._display()

    def _small_step_up(self, tkevent):
        _, this_max, this_step, _, _ = self.params[self.current_dial]
        this_value = self._VALUES[self.current_dial]
        new_value = this_value + this_step
        if new_value <= this_max:
            self._set_new_value(self.current_dial, new_value)

    def _big_step_up(self, tkevent):
        _, this_max, _, this_step, _ = self.params[self.current_dial]
        this_value = self._VALUES[self.current_dial]
        new_value = this_value + this_step
        if new_value <= this_max:
            self._set_new_value(self.current_dial, new_value)

    def _small_step_down(self, tkevent):
        this_min, _, this_step, _, _ = self.params[self.current_dial]
        this_value = self._VALUES[self.current_dial]
        new_value = this_value - this_step
        if new_value >= this_min:
            self._set_new_value(self.current_dial, new_value)

    def _big_step_down(self, tkevent):
        this_min, _, _, this_step, _ = self.params[self.current_dial]
        this_value = self._VALUES[self.current_dial]
        new_value = this_value - this_step
        if new_value >= this_min:
            self._set_new_value(self.current_dial, new_value)

    def _reset(self, _press=None):
        for dial in self.dial_names:
            default_value = self.params[dial][4]
            self._VALUES[dial] = default_value
            self._LABELS[dial] = self._get_new_label_part(dial, default_value)
        for SIM in (self.SIM, self.SIM_noSF):
            SIM.crystal.dxtbx_crystal.set_U(self.start_ori)
            SIM.instantiate_diffBragg(oversample=1, device_Id=0, default_F=0)
        self._generate_image_data(update_ref=True)
        self._display(init=True)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if "-h" in sys.argv:
            print(help_message)
            exit()
        if "-f" in sys.argv:
            sys.argv.remove("-f")
            pdbid = sys.argv[-1]
            try:
                pdbfile = get_pdb(pdbid, "pdb", "rcsb", log=sys.stdout, format="pdb")
            except Exception:
                import pdb; pdb.set_trace()
                print("Couldn't fetch pdb {}. Try fetching with iotbx.fetch_pdb.".format(pdbid))
                exit()
        else:
            pdbfile = sys.argv[1]
    else:
        pdbfile = libtbx.env.find_in_repositories(
            relative_path="sim_erice/4bs7.pdb",
            test=os.path.isfile)
        if not pdbfile:
            print("Could not load default model file. Please supply one on the command line.")
            exit()

    # params stored as: [min, max, small_step, big_step, default]
    params = {
        "DomainSize":[6, 200, 2, 10, 30],
        "MosAngDeg":[0.01, 5, 0.01, 0.1, 0.1001],
        "ucell_scale":[0.5, 2., 0.05, 0.1, 1],
        "Diff_gamma":[1, 1000, 1, 10, 50],
        "Diff_sigma":[.001, 5, .1, 1, .3001],
        "Aniso":[.01, 10, .01, .1, 1],
        "Energy":[6500, 12000, 10, 30, 9500],
        "Bandwidth":[0.01, 5.01, 0.1, 1, 0.31],
        "RotX": [-180, 180, 0.01, 0.1, 0],
        "RotY": [-180, 180, 0.01, 0.1, 0],
        "RotZ": [-180, 180, 0.01, 0.1, 0],
        "Fhkl":[0, 1, 1, 1, 1], # binary switch
        "Brightness":[0, 2, 0.01, 0.1, 0.5]}

    root = tk.Tk()
    root.title("SimView")

    root.geometry('940x500')
    #root.resizable(0,0)
    
    frame = SimView(root, params, pdbfile)
    
    frame.pack( side=tk.TOP, expand=tk.YES)
    root.mainloop()
#

