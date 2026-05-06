{
    const scalar hAvgBefore = gAverage(h.primitiveField());
    const scalar TAvgBefore = gAverage(thermo.T().primitiveField());
    const scalar cpAvg = gAverage(cp.primitiveField());
    const scalar rhoAvg = gAverage(rho.primitiveField());

    fvScalarMatrix hEqn
    (
        fvm::ddt(betav*rho, h)
        - (
            thermo.isotropic()
            ? fvm::laplacian(betav*thermo.alpha(), h, "laplacian(alpha,h)")
            : fvm::laplacian(betav*taniAlpha(), h, "laplacian(alpha,h)")
        )
        ==
        fvOptions(rho, h)
    );

    const scalar diagSum = gSum(hEqn.diag());
    const scalar sourceSum = gSum(hEqn.source());
    const scalar diag0 = hEqn.diag()[0];
    const scalar source0 = hEqn.source()[0];
    const scalar vol0 = mesh.V()[0];
    const scalar h0Before = h[0];

    if (!coupled)
    {
        hEqn.relax();
    }

    fvOptions.constrain(hEqn);

    if (coupled)
    {
        fvMatrixAssemblyPtr->addFvMatrix(hEqn);
    }
    else
    {
        Info<< "\nSolving for solid region "<< solidRegions[i].name() << endl;

        if (finalIter)
        {
            mesh.data().setFinalIteration(true);
        }

        hEqn.solve(h.select(finalIter));

        const scalar hAvgPostSolve = gAverage(h.primitiveField());
        const scalar h0PostSolve = h[0];

        fvOptions.correct(h);

        const scalar hAvgPostFvOptions = gAverage(h.primitiveField());

        thermo.correct();

        const scalar hAvgAfter = gAverage(h.primitiveField());
        const scalar TAvgAfter = gAverage(thermo.T().primitiveField());
        Info<< "EnergyDebug region " << solidRegions[i].name()
            << " time " << mesh.time().value()
            << " rhoAvg " << rhoAvg
            << " cpAvg " << cpAvg
            << " diagSum " << diagSum
            << " sourceSum " << sourceSum
            << " vol0 " << vol0
            << " diag0 " << diag0
            << " source0 " << source0
            << " hAvgBefore " << hAvgBefore
            << " h0Before " << h0Before
            << " hAvgPostSolve " << hAvgPostSolve
            << " h0PostSolve " << h0PostSolve
            << " hAvgPostFvOptions " << hAvgPostFvOptions
            << " hAvgAfter " << hAvgAfter
            << " TAvgBefore " << TAvgBefore
            << " TAvgAfter " << TAvgAfter
            << endl;

        Info<< "Min/max T:" << min(thermo.T()).value() << ' '
            << max(thermo.T()).value() << endl;

        if (finalIter)
        {
            mesh.data().setFinalIteration(false);
        }
    }
}
