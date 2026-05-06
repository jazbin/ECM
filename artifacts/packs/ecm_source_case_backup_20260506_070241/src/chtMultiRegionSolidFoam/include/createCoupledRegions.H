bool coupled = false;
bool allowImplicitSolidsOnly = false;
bool debugImplicitCoupling = false;
{
    fvSolution solutionDict(runTime);
    solutionDict.readIfPresent("coupledEnergyField", coupled);
    solutionDict.readIfPresent("allowImplicitSolidsOnly", allowImplicitSolidsOnly);
    solutionDict.readIfPresent("debugImplicitCoupling", debugImplicitCoupling);
}

autoPtr<fvMatrix<scalar>> fvMatrixAssemblyPtr;

bool forcedExplicit = false;
if (!fluidRegions.size() && solidRegions.size())
{
    if (!allowImplicitSolidsOnly)
    {
        forAll(solidRegions, i)
        {
            solidThermo& thermo = thermos[i];
            auto& bpsi = thermo.T().boundaryFieldRef();
            auto& bhe = thermo.he().boundaryFieldRef();

            forAll(bpsi, patchI)
            {
                if (bpsi[patchI].useImplicit() || bhe[patchI].useImplicit())
                {
                    bpsi[patchI].useImplicit(false);
                    bhe[patchI].useImplicit(false);
                    forcedExplicit = true;
                }
            }
        }
    }

    if (forcedExplicit)
    {
        WarningInFunction
            << "Solids-only case detected: disabling implicit interface"
            << " coupling (useImplicit=false) to avoid non-physical"
            << " undershoot. Use explicit coupling or fix fvMatrixAssembly"
            << " path before enabling useImplicit." << endl;
        coupled = false;
    }
    else if (allowImplicitSolidsOnly)
    {
        WarningInFunction
            << "Solids-only case: allowImplicitSolidsOnly=true; implicit"
            << " interface coupling enabled (experimental, known"
            << " fvMatrixAssembly undershoot risk)." << endl;
    }
}

forAll(fluidRegions, i)
{
    const rhoThermo& thermo = refCast<const rhoThermo>(thermoFluid[i]);
    const auto& bpsi = thermo.T().boundaryField();

    forAll(bpsi, patchI)
    {
        if (bpsi[patchI].useImplicit())
        {
            coupled = true;
        }
    }
}

forAll(solidRegions, i)
{
    solidThermo& thermo = thermos[i];
    const auto& bpsi = thermo.T().boundaryField();

    forAll(bpsi, patchI)
    {
        if (bpsi[patchI].useImplicit())
        {
            coupled = true;
        }
    }
}

forAll(fluidRegions, i)
{
    const rhoThermo& thermo = refCast<const rhoThermo>(thermoFluid[i]);
    if (coupled)
    {
        Info<< "Create fvMatrixAssembly." << endl;
        fvMatrixAssemblyPtr.reset
        (
            new fvMatrix<scalar>
            (
                thermo.he(),
                dimEnergy/dimTime
            )
        );
        break;
    }
}

if (coupled && !fvMatrixAssemblyPtr)
{
    forAll(solidRegions, i)
    {
        solidThermo& thermo = thermos[i];
        Info<< "Create fvMatrixAssembly." << endl;
        fvMatrixAssemblyPtr.reset
        (
            new fvMatrix<scalar>
            (
                thermo.he(),
                dimEnergy/dimTime
            )
        );
        break;
    }
}
