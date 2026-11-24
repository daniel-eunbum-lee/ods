# References

1. **Allemang, R. J., & Brown, D. L.** (1982). A correlation coefficient for modal vector analysis. *Proceedings of the 1st International Modal Analysis Conference (IMAC)*, 110–116. Source of the MAC.
2. **Bendat, J. S., & Piersol, A. G.** (2010). *Random Data: Analysis and Measurement Procedures* (4th ed.). Wiley. Source of the H1 estimator, coherence and random errors of spectral estimates.
3. **Blevins, R. D.** (1979). *Formulas for Natural Frequency and Mode Shape*. Van Nostrand Reinhold. Table 8-1: cantilever frequency equation 1 + cos λ cosh λ = 0 and its roots, used by the analytical benchmark.
4. **Brincker, R., & Ventura, C. E.** (2015). *Introduction to Operational Modal Analysis*. Wiley. Background on output-only OMA (FDD, SSI).
5. **NAVMAT P-9492** (1979). *Navy Manufacturing Screening Program*. Department of the Navy. Source of the random-vibration screening profile used for the synthetic input.
6. **Pappa, R. S., Elliott, K. B., & Schenk, A.** (1993). Consistent-mode indicator for the eigensystem realization algorithm. *Journal of Guidance, Control, and Dynamics*, 16(5), 852–858. Source of the MPC.
7. **Richardson, M. H.** (1997). Is it a mode shape, or an operating deflection shape? *Sound & Vibration*, 31(1), 54–61. Background on ODS vs. mode shapes.
8. **Welch, P. D.** (1967). The use of fast Fourier transform for the estimation of power spectra: A method based on time averaging over short, modified periodograms. *IEEE Transactions on Audio and Electroacoustics*, 15(2), 70–73. Source of Welch averaging.
9. **SciPy** `scipy.signal.csd`, `welch`, `find_peaks`: <https://docs.scipy.org/doc/scipy/reference/signal.html>.

## Software quality assurance (see [sqa.md](sqa.md))

These informed the graded, lightweight approach used here. The project does not claim compliance with any of them.

10. **IEEE** (Std 730). *IEEE Standard for Software Quality Assurance Processes*. No edition is cited on purpose; consult the [IEEE Standards Association](https://standards.ieee.org) for the current one.
11. **IEEE** (Std 1012-2024). *IEEE Standard for System, Software, and Hardware Verification and Validation*. The 2016 edition is superseded: <https://standards.ieee.org/ieee/1012/7324>.
12. **ASME** (2019). *V&V 10-2019: Standard for Verification and Validation in Computational Solid Mechanics*: <https://www.asme.org/codes-standards/find-codes-standards/standard-for-verification-and-validation-in-computational-solid-mechanics/2019>.
13. **NASA** (2022). *NASA-STD-8739.8B: Software Assurance and Software Safety Standard*: <https://standards.nasa.gov/standard/NASA/NASA-STD-87398>. Approval date from the NASA Software Engineering Handbook.
14. **Wilson, G., Bryan, J., Cranston, K., Kitzes, J., Nederbragt, L., & Teal, T. K.** (2017). Good enough practices in scientific computing. *PLOS Computational Biology*, 13(6), e1005510. <https://doi.org/10.1371/journal.pcbi.1005510>.
