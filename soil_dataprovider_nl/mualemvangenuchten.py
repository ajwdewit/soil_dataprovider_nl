# -*- coding: utf-8 -*-
# Copyright (c) 2026 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), April 2026
# Mualem van Genuchten functions based on R code provided by Martin Mulder
from dataclasses import dataclass
# #' Get water content based on pressure head
# #'
# #' @param H pressure head [cm].
# #' @param WCR residual water content [cm3 cm-3].
# #' @param WCS saturated water content [cm3 cm-3].
# #' @param ALPHA curve shape parameter [-].
# #' @param NPAR curve shape parameter [-].
# #' @return return water content [cm3 cm-3].
# #' @keywords internal
# get_wc_MvG  <- function(H, WCR, WCS, ALPHA, NPAR) {
#
#   # --- main part of procedure ---
#
#   m <- 1 - 1 / NPAR
#   wc <- WCR + (WCS - WCR) / ((1 + (ALPHA * H)^NPAR)^m)
#
#   # --- return of procedure ---
#
#   return (wc)

@dataclass()
class MualemvanGenuchten:
    wcr: float
    wcs:float
    alpha: float
    npar: float
    lamda: float
    ksat: float


def get_water_content_from_MvG(H, p):
    """return volumetric water content for given pressure head H [cm] and MvG parameters p.

    :param H: pressure head [cm].
    :param p: Object representing MvG parameters having attributes:
        - wcr: residual water content [cm3 cm-3].
        - wcs: saturated water content [cm3 cm-3].
        - alpha: curve shape parameter [-].
        - npar: curve shape parameter [-].
    :return: (array of) water content values for given MvG parameters
    """
    m = 1.0 - 1.0 / p.npar
    wc = p.wcr + (p.wcs - p.wcr) / ((1 + (p.alpha * H) ** p.npar) ** m)

    return wc



#' Get conductivity based on pressure head
#'
#' @param H pressure head [cm]
#' @param ALPHA curve shape parameter [-]
#' @param NPAR curve shape parameter [-]
#' @param LAMBDA exponent in hydraulic conductivity function [-]
#' @param KSAT hydraulic conductivity of saturated soil [cm d-1]
#' @return return conductivity [cm d-1]
#' @keywords internal
# get_cond_MvG  <- function(H, ALPHA, NPAR, LAMBDA, KSAT) {
#
#   # --- main part of procedure ---
#
#   m <- 1 - 1 / NPAR
#   ah <- ALPHA * H
#   h1 <- (1 + ah^NPAR)^m
#   h2 <- ah**(NPAR - 1)
#   denom <- (1 + ah^NPAR)^(m*(LAMBDA + 2))
#   cond <- KSAT * (h1 - h2)^2 / denom
#
#   # --- return of procedure ---
#
#   return (cond)
# }

def get_conductivity_from_MvG(H, p):
    """Get conductivity from pressure head H [cm] and MvG parameters p.

    :param H: pressure head [cm]
    :param p: Object representing MvG parameters having attributes:
        - alpha: curve shape parameter [-]
        - npar: curve shape parameter [-]
        - lamda: exponent in hydraulic conductivity function [-]
        - ksat: hydraulic conductivity of saturated soil [cm d-1]
    :return: conductivity [cm d-1]
    """

    m = 1 - 1 / p.npar
    ah = p.alpha * H
    h1 = (1 + ah ** p.npar) ** m
    h2 = ah ** (p.npar - 1)
    denom = (1 + ah ** p.npar) ** (m * (p.lamda + 2))
    cond = p.ksat * (h1 - h2)**2 / denom

    return cond