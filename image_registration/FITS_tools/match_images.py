from image_registration import chi2_shift
try:
    import astropy.io.fits as pyfits
    import astropy.wcs as pywcs
except ImportError:
    import pyfits
    import pywcs

def project_to_header(fitsfile, header, use_montage=True, **kwargs):
    """
    Light wrapper of montage with hcongrid as a backup
    """
    try:
        import montage
        montageOK=True
    except ImportError:
        montageOK=False
    try:
        from hcongrid import hcongrid
        hcongridOK=True
    except ImportError:
        hcongridOK=False
    import tempfile

    if montageOK and use_montage:
        temp_headerfile = tempfile.NamedTemporaryFile()
        header.toTxtFile(temp_headerfile.name)

        outfile = tempfile.NamedTemporaryFile()
        montage.wrappers.reproject(fitsfile, outfile.name,
                temp_headerfile.name, exact_size=True,
                silent_cleanup=quiet)
        image = pyfits.getdata(outfile.name)
        
        outfile.close()
        temp_headerfile.close()
    elif hcongridOK:
        image = hcongrid( pyfits.getdata(fitsfile),
                pyfits.getheader(fitsfile), header)

    return image

def match_fits(fitsfile1, fitsfile2, header=None, quiet=True, sigma_cut=False,
        return_header=False, **kwargs):
    """
    Determine the shift between two FITS images using the cross-correlation
    technique.  Requires montage or scipy.

    Parameters
    ----------
    fitsfile1: str
        Reference fits file name
    fitsfile2: str
        Offset fits file name
    header: pyfits.Header
        Optional - can pass a header to projet both images to
    quiet: bool
        Silence messages?
    sigma_cut: bool or int
        Perform a sigma-cut on the returned images at this level
    """

    if header is None:
        header = pyfits.getheader(fitsfile1)
        image1 = pyfits.getdata(fitsfile1)
    else: # project image 1 to input header coordinates
        image1 = project_to_header(fitsfile1, header)

    # project image 2 to image 1 coordinates
    image2_projected = project_to_header(fitsfile2, header)

    if image1.shape != image2_projected.shape:
        raise ValueError("Failed to reproject images to same shape.")

    if sigma_cut:
        corr_image1 = image1*(image1 > image1.std()*sigma_cut)
        corr_image2 = image2_projected*(image2_projected > image2_projected.std()*sigma_cut)
        OK = (corr_image1==corr_image1)*(corr_image2==corr_image2) 
        if (corr_image1[OK]*corr_image2[OK]).sum() == 0:
            print "Could not use sigma_cut of %f because it excluded all valid data" % sigma_cut
            corr_image1 = image1
            corr_image2 = image2_projected
    else:
        corr_image1 = image1
        corr_image2 = image2_projected

    returns = corr_image1, corr_image2
    if return_header:
        returns = returns + (header,)
    return returns

def register_FITS(fitsfile1, fitsfile2, errfile=None,
        register_method=chi2_shift, return_cropped_images=False, **kwargs):
    """
    Determine the shift between two FITS images using the cross-correlation
    technique.  Requires montage or hcongrid.

    Parameters
    ----------
    fitsfile1: str
        Reference fits file name
    fitsfile2: str
        Offset fits file name
    return_cropped_images: bool
        Returns the images used for the analysis in addition to the measured
        offsets
    quiet: bool
        Silence messages?
    sigma_cut: bool or int
        Perform a sigma-cut before cross-correlating the images to minimize
        noise correlation?
    """
    corr_image1, corr_image2, header = match_fits(fitsfile1, fitsfile2,
            return_header=True, **kwargs)

    if errfile is not None:
        errimage = project_to_header(errfile, header, **kwargs)
    else:
        errimage = None

    xoff,yoff = register_method(corr_image1, corr_image2, err=errimage, **kwargs)
    
    wcs = pywcs.WCS(header)
    try:
        cdelt = wcs.wcs.cd.diagonal()
    except AttributeError:
        cdelt = wcs.wcs.cdelt
    xoff_wcs,yoff_wcs = np,array([xoff,yoff])*cdelt
    #try:
    #    xoff_wcs,yoff_wcs = np.inner( np.array([[xoff,0],[0,yoff]]), wcs.wcs.cd )[[0,1],[0,1]]
    #except AttributeError:
    #    xoff_wcs,yoff_wcs = 0,0

    if return_cropped_images:
        return xoff,yoff,xoff_wcs,yoff_wcs,image1,image2_projected
    else:
        return xoff,yoff,xoff_wcs,yoff_wcs
    

