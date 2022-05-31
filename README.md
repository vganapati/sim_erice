# sim_erice

Bragg simulation and model fitting frontend

## SimView: lightweight simulator and viewer for diffraction still images.

Run without any arguments, this program simulates diffraction of a small lysozyme crystal. You may provide a different pdb file on the command line instead, or may request the program fetch one from the PDB by supplying its PDB ID and the -f flag (for "fetch"). If this fails you may want to try using the command line program "iotbx.fetch_pdb" instead.

Diffraction from your crystal will be simulated with a set of default parameters for mosaic block size, beam energy and bandpass, etc. that you can change by adjusting each of the dials. Parameters to be adjusted can be selected either with the drop-down menu or with keyboard shortcuts as follows:


**Left arrow or p:**    previous parameter

**Right arrow or n:**   next parameter

**Up arrow:**           increase this parameter

**Down arrow:**         decrease this parameter

**Shift-up arrow:**     increase this parameter a lot

**Shift-down arrow:**   decrease this parameter a lot

**Space bar:**          simulate a new stochastic XFEL pulse

**R:**                  reset all parameters to defaults

**I:**                  toggle between image display modes

**S:**                  toggle spectrum shape

**O:**                  randomize crystal orientation

**U:**                  update reference image (in red)


(Note that matplotlib binds the left arrow key to resetting the field of view, so both this effect and selection of the previous parameter will take place if you are zoomed in on an area. The right arrow key can restore the zoom.)

## Explanation of parameters:

**DomainSize:** the small blocks within crystals that are internally perfectly aligned and identical are called mosaic domains. The average size of a domain is one contributing factor determining the sharpness of the Bragg peaks. As the size of the mosaic domain increases, the effect of constructive interference of the scattered X-rays gets stronger, and the peak sharpens.

**MosAngDeg:** the mosaic domains are misoriented relative to one another by an average angle denoted the mosaic angle, displayed here in degrees. Larger differences in the orientations of the domains produce contributions to Bragg peaks over a wider area on the detector, resulting in more diffuse spots.

**a, b, c:** the parameters of the crystal unit cell. Depending on the symmetry of the crystal, these may all vary independently or may be constrained to scale together, in which case not all unit cell lengths will be exposed as adjustible dials. Larger unit cells produce constructive and destructive interference at smaller angles, resulting in more closely spaced Bragg peaks on the detector.

**Missetting angles:** differences between the true orientation of the crystal and what is determined during indexing. A misorientation of the X or Y axis means a misestimation of which spots are in diffracting conditions, and will affect which spots (or how much of the spots) appear on the detector. Since the Z axis is along the beam direction, misorientation in Z results in rotation of the entire diffraction pattern.

**Energy/Bandwidth:** the energy of the X-ray beam denotes the average energy of an individual pulse. For X-ray free electron laser (XFEL) pulses generated by self-amplified spontaneous emission (SASE), each pulse is spiky and stochastic, with a typical bandwidth of between 10 and 30 eV. A monochromater may be used to narrow this to around 1 eV.

**Spectrum shape:** to simulate images with real SASE spectra, toggle this option to "SASE". To display diffraction produced by a smooth Gaussian function that can be adjusted in energy and bandwidth, toggle this to "Gaussian". SASE spectra are stochastic and will intentionally not be modified by the energy and bandwidth controls. The "monochromatic" option is recommended when diffuse scattering is enabled, to offset the greater computational cost.

**Fhkl:** when we observe diffraction from a single particle, we are seeing the Fourier transform of the particle, with [a great deal of] added noise. For many copies of a particle all in the same orientation, we can expect the signal to be much stronger. If these aligned particles are also periodically spaced, as in the context of a crystal, they act as a diffraction grating, and we see this signal only at positions of constructive interference (the reciprocal lattice points in diffracting conditions, i.e. Bragg peaks). In order to better see the effects of the above parameters, we can ignore the Fourier transform of the asymmetric unit and pretend all of the Bragg peaks have uniform intensity. This is what we are simulating when we display "SFs on/off".

**Diffuse scattering:** this physical effect is a result of variation and imperfection within the crystal and surrounding solvent, and it appears as X-ray scattering between and around the Bragg peaks. Modeling this can be toggled on or off. It is recommended to use the monochromatic spectrum setting when calculating diffuse signal.

**Diff_gamma and diff_sigma:** parameters describing the diffuse scattering signal produced by long-range correlations. Gamma denotes the correlation length in Ångstroms and sigma squared is the amplitude of the correlated vibrations in square Ångstroms.

**Diff_aniso:** anisotropic quality to the diffuse scattering. This is arbitrarily assigned directionality, and the adjustible parameter controls the degree to which this effect is observed.

**Further notes on the image viewer:** a random orientation can be assigned to the crystal by pressing the "Randomize orientation" button any number of times. Both the simulated and reference image update in this event. Outside of this situation, the reference image will be identical to your starting default parameters and can be updated to current parameters by pressing "Update reference". This can help highlight the difference between selected combinations of parameters. Finally, the viewer has two display modes, one in which the reference image is displayed in red and the current simulation is displayed in blue (with perfect overlap resulting in white or gray), and one in which only the simulation is shown. You can toggle "Reference image" to switch between these.
