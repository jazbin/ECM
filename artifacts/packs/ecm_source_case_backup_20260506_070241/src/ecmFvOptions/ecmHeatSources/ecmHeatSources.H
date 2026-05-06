/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | www.openfoam.com
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

#ifndef Foam_fv_ecmHeatSources_H
#define Foam_fv_ecmHeatSources_H

#include "cellSetOption.H"
#include "Function1.H"

namespace Foam
{
namespace fv
{

class ecmHeatSource
:
    public cellSetOption
{
    word qFieldName_;

    void addSupInternal(fvMatrix<scalar>& eqn, const label fieldi);

public:

    TypeName("ecmHeatSource");

    ecmHeatSource
    (
        const word& name,
        const word& modelType,
        const dictionary& dict,
        const fvMesh& mesh
    );

    virtual bool read(const dictionary& dict);

    virtual void addSup(fvMatrix<scalar>& eqn, const label fieldi);

    virtual void addSup
    (
        const volScalarField& rho,
        fvMatrix<scalar>& eqn,
        const label fieldi
    );
};


class uniformPowerHeatSource
:
    public cellSetOption
{
    scalar qdot_;
    scalar totalPower_;
    scalar domainFraction_;
    bool useFixedQdot_;
    autoPtr<Function1<scalar>> powerScale_;

    scalar qdotValue() const;
    void addSupInternal(fvMatrix<scalar>& eqn, const label fieldi);

public:

    TypeName("uniformPowerHeatSource");

    uniformPowerHeatSource
    (
        const word& name,
        const word& modelType,
        const dictionary& dict,
        const fvMesh& mesh
    );

    virtual bool read(const dictionary& dict);

    virtual void addSup(fvMatrix<scalar>& eqn, const label fieldi);

    virtual void addSup
    (
        const volScalarField& rho,
        fvMatrix<scalar>& eqn,
        const label fieldi
    );
};

} // End namespace fv
} // End namespace Foam

#endif
