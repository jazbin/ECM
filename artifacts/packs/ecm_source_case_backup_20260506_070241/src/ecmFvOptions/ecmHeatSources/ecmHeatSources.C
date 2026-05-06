/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | www.openfoam.com
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

#include "ecmHeatSources.H"
#include "addToRunTimeSelectionTable.H"
#include "fvMatrices.H"
#include "volFields.H"
#include "Time.H"

namespace Foam
{
namespace fv
{
    defineTypeNameAndDebug(ecmHeatSource, 0);
    addToRunTimeSelectionTable(option, ecmHeatSource, dictionary);

    defineTypeNameAndDebug(uniformPowerHeatSource, 0);
    addToRunTimeSelectionTable(option, uniformPowerHeatSource, dictionary);
}
}


Foam::fv::ecmHeatSource::ecmHeatSource
(
    const word& name,
    const word& modelType,
    const dictionary& dict,
    const fvMesh& mesh
)
:
    cellSetOption(name, modelType, dict, mesh),
    qFieldName_("ecmQdot")
{
    if (isActive())
    {
        read(dict);
    }
}


bool Foam::fv::ecmHeatSource::read(const dictionary& dict)
{
    if (!cellSetOption::read(dict))
    {
        return false;
    }

    qFieldName_ = coeffs_.getOrDefault<word>("qField", "ecmQdot");
    fieldNames_ = coeffs_.getOrDefault<wordList>("fields", wordList(1, "h"));
    resetApplied();
    return true;
}


void Foam::fv::ecmHeatSource::addSupInternal
(
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    if (!mesh_.foundObject<volScalarField>(qFieldName_))
    {
        return;
    }

    const volScalarField& qVol = mesh_.lookupObject<volScalarField>(qFieldName_);

    forAll(cells_, i)
    {
        const label celli = cells_[i];
        eqn.source()[celli] -= qVol[celli]*mesh_.V()[celli];
    }

    setApplied(fieldi);
}


void Foam::fv::ecmHeatSource::addSup
(
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    addSupInternal(eqn, fieldi);
}


void Foam::fv::ecmHeatSource::addSup
(
    const volScalarField&,
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    addSupInternal(eqn, fieldi);
}


Foam::fv::uniformPowerHeatSource::uniformPowerHeatSource
(
    const word& name,
    const word& modelType,
    const dictionary& dict,
    const fvMesh& mesh
)
:
    cellSetOption(name, modelType, dict, mesh),
    qdot_(0),
    totalPower_(0),
    domainFraction_(1),
    useFixedQdot_(false),
    powerScale_(nullptr)
{
    if (isActive())
    {
        read(dict);
    }
}


bool Foam::fv::uniformPowerHeatSource::read(const dictionary& dict)
{
    if (!cellSetOption::read(dict))
    {
        return false;
    }

    fieldNames_ = coeffs_.getOrDefault<wordList>("fields", wordList(1, "h"));
    useFixedQdot_ = coeffs_.readIfPresent("qdot", qdot_);
    powerScale_.clear();

    if (!useFixedQdot_)
    {
        coeffs_.readEntry("totalPower", totalPower_);
        domainFraction_ = coeffs_.getOrDefault<scalar>("domainFraction", 1.0);
    }

    if (coeffs_.found("powerScale"))
    {
        powerScale_ = Function1<scalar>::New("powerScale", coeffs_);
    }

    resetApplied();
    return true;
}


Foam::scalar Foam::fv::uniformPowerHeatSource::qdotValue() const
{
    const scalar scale =
        powerScale_.valid()
      ? powerScale_->value(mesh_.time().value())
      : scalar(1);

    if (useFixedQdot_)
    {
        return scale*qdot_;
    }

    return V_ > SMALL ? scale*domainFraction_*totalPower_/V_ : 0.0;
}


void Foam::fv::uniformPowerHeatSource::addSupInternal
(
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    const scalar qdot = qdotValue();

    forAll(cells_, i)
    {
        const label celli = cells_[i];
        eqn.source()[celli] -= qdot*mesh_.V()[celli];
    }

    setApplied(fieldi);
}


void Foam::fv::uniformPowerHeatSource::addSup
(
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    addSupInternal(eqn, fieldi);
}


void Foam::fv::uniformPowerHeatSource::addSup
(
    const volScalarField&,
    fvMatrix<scalar>& eqn,
    const label fieldi
)
{
    addSupInternal(eqn, fieldi);
}
