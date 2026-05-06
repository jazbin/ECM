/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | ECM coupling functionObject
    \\  /    A nd           | (temperature -> volumetric heat source)
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

#ifndef functionObjects_ecmCoupler_H
#define functionObjects_ecmCoupler_H

#include "fvMeshFunctionObject.H"
#include "volFields.H"
#include "cellZoneMesh.H"
#include "dictionary.H"
#include "word.H"
#include "Switch.H"
#include "globalIndex.H"
#include "Pstream.H"
#include "vector.H"

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <unordered_map>

#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>

namespace Foam
{
namespace functionObjects
{

class ecmCoupler : public fvMeshFunctionObject
{
    // Private data

        // Dict
        dictionary dict_;

        // Selection
        word zoneName_;
        word TName_;

        // Output
        word qFieldName_;     // W/m^3
        word stFieldName_;    // K/s (optional)

        // Coupling mode
        word couplingMode_;   // "elementWise" or "lumped"
        word lumpedOutput_;   // "volumetric" or "totalPower"
        scalar totalVolumeScale_; // scale zone volume before totalPower division (e.g. 72 for 5° wedge = 360/5)

        // Mode
        word outputMode_;     // "volumetricHeat" or "temperatureSource"
        scalar rhoCp_;        // J/m^3/K for temperatureSource conversion
        word tEffMode_;       // "volumeAverage", "coreWeighted", "sensorEmulation"
        word sensorZoneName_; // optional cellZone name for sensorEmulation
        vector coreAxis_;     // axis for coreWeighted (normalized internally)
        vector coreOrigin_;   // origin for coreWeighted
        word axialProfile_;   // "uniform" or "linear"
        vector axialAxis_;    // axis for axial profile
        vector axialOrigin_;  // origin for axial profile
        scalar axialBias_;    // -1..1 bias for linear profile

        // Coupling
        fileName inFile_;
        fileName outFile_;
        fileName lastGoodFile_;
        word ioMode_;         // "binary" or "cliWrapper"
        word parallelMode_;   // "serialOnly" or "masterGather"
        word keyMode_;        // "globalCellId" or "localCellId"

        scalar relaxAlpha_;   // 0..1
        Switch writeFields_;
        Switch adaptiveRelaxation_;
        scalar alphaMin_;
        scalar alphaMax_;
        scalar alphaIncrease_;
        scalar alphaDecrease_;
        scalar deltaQThreshold_;
        scalar deltaTThreshold_;
        scalar alpha_;
        scalar lastTEff_;
        word missingOutputAction_;
        label missingOutputLimit_;
        label missingOutputCount_;
        bool degradedMode_;
        label subIterations_;
        word subIterationResult_;
        word temporalInterpolation_; // "hold" or "linear"

        // External command
        string command_;
        string wrapperCommand_;

        // CLI wrapper (lumped, CSV-output) mode
        word wrapperMode_;         // e.g., "single"
        word wrapperTempMode_;     // e.g., "coupled"
        word wrapperTempProfile_;  // e.g., "constant"
        word wrapperCurrentProfile_; // e.g., "constant"
        label wrapperSteps_;       // steps per invocation (typically 1)
        fileName wrapperCsvPrefix_;
        fileName wrapperCsvFile_;
        Switch wrapperWriteCsv_;
        string wrapperExtraArgs_;
        scalar wrapperTempOffsetC_; // add to T [K] to get degC
        word wrapperHeatColumn_;
        word wrapperQAhColumn_;
        word wrapperVrc1Column_;
        word wrapperVrc2Column_;
        word wrapperHysteresisColumn_;
        word wrapperVoltageColumn_;
        scalar currentA_;
        scalar currentSign_;
        scalar qAh_;
        scalar vRc1_;
        scalar vRc2_;
        scalar hysteresis_;
        Switch wrapperStateReset_;
        fileName wrapperStateFile_;
        fileName checkpointDir_;
        fileName writeTimeHistoryFile_;

        // Electrical inputs (name/value)
        word inputMode_;      // "constant" or "csv"
        fileName inputFile_;
        word inputTimeColumn_;
        List<scalar> inputTimes_;
        List<List<scalar>> inputSeries_;
        bool inputSeriesLoaded_;
        List<word> inputNames_;
        List<scalar> inputValues_;

        // Transaction tracking
        uint64_t stepId_;
        uint64_t lastGoodStepId_;
        scalar lastGoodTime_;
        scalar lastGoodQSum_;
        label lastReturnCode_;
        HashTable<scalar, label> lastGoodQByKey_;

        // Persistent wrapper process (ioMode=persistentPipe)
        pid_t    persistentPid_;
        int      persistentStdinFd_;
        int      persistentStdoutFd_;

        // Element mapping: aggregate N cells → M ECM elements before ECM call
        fileName elementMappingFile_;
        bool hasElementMapping_;
        std::unordered_map<int,int> cellToEcmElement_;  // globalCellId → ecmElementId
        label nEcmElements_;

        // C++ step counter: skip pipe entirely on non-real-ECM steps
        label callEveryNSteps_;   // call ECM every N CFD steps (default 1 = every step)
        label callStepCounter_;   // steps elapsed since last real ECM call
        scalar accumulatedDt_;    // accumulated deltaT since last real ECM call
        bool restartCheckpointRestored_; // true when exact time checkpoint restored
        bool restartCheckpointReconstructed_; // true when startup q is rebuilt from nearby checkpoints
        string restartReconstructionInfo_;


    // Private Member Functions

        void readElectricalInputs(const dictionary& d);

        bool loadElectricalInputsCsv();

        bool updateElectricalInputsFromCsv(const scalar timeValue);

        labelList zoneCells() const;

        labelList cellKeys(const labelList& cells) const;

        bool writeInput(const labelList& keys, const scalarField& Tvals, const uint64_t stepId) const;

        bool writeInputWithTime(
            const labelList& keys,
            const scalarField& Tvals,
            const uint64_t stepId,
            const scalar timeValue,
            const scalar deltaT
        ) const;

        bool runExternal();

        bool readOutput(HashTable<scalar, label>& qByKey, const uint64_t expectedStepId, uint64_t& outStepId) const;

        bool writeLastGoodSnapshot(
            const HashTable<scalar, label>& qByKey,
            const uint64_t stepId,
            const scalar timeValue,
            const scalar qSum,
            const label returnCode
        ) const;

        bool readLastGoodSnapshot();
        bool writeRestartCheckpoint() const;
        bool writeWriteTimeHistory() const;
        bool restoreRestartCheckpoint();
        bool restoreRestartCheckpointFallback();
        void updateDerivedFilePaths();
        fileName checkpointPathForTime(const fileName& timeName) const;
        static bool copyFileContents(const fileName& src, const fileName& dst);

        bool writeWrapperJsonInput(
            const scalar TcellC,
            const scalar dt,
            const scalar timeValue,
            const scalar currentA,
            const uint64_t stepId
        ) const;

        bool readWrapperJsonOutput(scalar& qOut, scalar& vT) const;

        void ensureFields();

        scalar updateFieldsElementWise(const labelList& keys, const HashTable<scalar, label>& qByKey);

        scalar updateFieldsLumped(const labelList& cells, const label lumpedKey, const HashTable<scalar, label>& qByKey);

        scalar computeTEff(const labelList& cells, const volScalarField& T) const;

        scalar lookupInputOrDefault(const word& name, const scalar fallback) const;

        string buildWrapperCommand(const scalar TcellC, const scalar dt) const;

        bool readWrapperCsv(scalar& qOut, scalar& vT);

        void loadElementMapping();

        bool startPersistentWrapper();
        bool callPersistentWrapper(const std::string& request, std::string& response);
        bool callPersistentWrapperBinary(const std::string& request, std::string& response);
        void stopPersistentWrapper();
        std::string buildWrapperRequestJson(const scalar TcellC, const scalar dt, const scalar timeValue, const scalar currentA, const uint64_t stepId) const;
        std::string buildElementWisePipeRequestJson(const labelList& keys, const scalarField& Tvals, const scalar dt, const scalar timeValue, const uint64_t stepId, const scalar tEffK) const;
        std::string buildElementWisePipeRequestBinary(const labelList& keys, const scalarField& Tvals, const scalar dt, const scalar timeValue, const uint64_t stepId, const scalar tEffK) const;
        bool parseOutputBuffer(const std::string& buffer, HashTable<scalar, label>& qByKey, const uint64_t expectedStepId, uint64_t& outStepId) const;
        void initializeStartupFields();


public:

    TypeName("ecmCoupler");

    // Constructors
    ecmCoupler
    (
        const word& name,
        const Time& runTime,
        const dictionary& dict
    );

    //- Destructor
    virtual ~ecmCoupler();

    // Member Functions
    virtual bool read(const dictionary& dict);

    virtual bool execute();

    virtual bool write();
};

} // End namespace functionObjects
} // End namespace Foam

#endif
