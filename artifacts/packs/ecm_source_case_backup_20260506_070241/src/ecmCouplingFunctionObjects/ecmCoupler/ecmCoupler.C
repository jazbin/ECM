/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | ECM coupling functionObject
    \\  /    A nd           | (temperature -> volumetric heat source)
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/


// Terminology:
// - "battery cell" = physical electrochemical unit represented by the external ECM (single electrical state).
// - "mesh cell"    = OpenFOAM finite-volume control volume. This coupling exchanges data per mesh cell inside a cellZone.
// - Keys in the IO protocol identify mesh cells, not battery cells.

#include "ecmCoupler.H"

#include "addToRunTimeSelectionTable.H"
#include "OSspecific.H"
#include "IOobject.H"
#include "Time.H"
#include "dimensionedScalar.H"
#include "unitConversion.H"
#include "PstreamReduceOps.H"

#include <cstdint>
#include <cstring>
#include <algorithm>
#include <sstream>
#include <cctype>
#include <cstdlib>
#include <iomanip>
#include <cmath>
#include <limits>
#include <dirent.h>
#include <cstdio>

#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>

namespace Foam
{
namespace functionObjects
{
    defineTypeNameAndDebug(ecmCoupler, 0);
    addToRunTimeSelectionTable(functionObject, ecmCoupler, dictionary);
}
}

using namespace Foam;
using namespace Foam::functionObjects;

namespace
{
    label parseCallEveryNStepsFromCommand(const string& cmd, const label fallback)
    {
        std::istringstream iss(cmd);
        std::string tok;
        while (iss >> tok)
        {
            if (tok == "--ecm-call-every-n-steps")
            {
                std::string val;
                if (!(iss >> val))
                {
                    return fallback;
                }
                try
                {
                    const long n = std::stol(val);
                    return (n > 0) ? static_cast<label>(n) : fallback;
                }
                catch (const std::exception&)
                {
                    return fallback;
                }
            }

            const std::string key = "--ecm-call-every-n-steps=";
            if (tok.rfind(key, 0) == 0 && tok.size() > key.size())
            {
                try
                {
                    const long n = std::stol(tok.substr(key.size()));
                    return (n > 0) ? static_cast<label>(n) : fallback;
                }
                catch (const std::exception&)
                {
                    return fallback;
                }
            }
        }
        return fallback;
    }

    string parseOptionValueFromCommand(const string& cmd, const std::string& option)
    {
        std::istringstream iss(cmd);
        std::string tok;
        while (iss >> tok)
        {
            if (tok == option)
            {
                std::string val;
                if (iss >> val)
                {
                    return string(val);
                }
                return string("");
            }

            const std::string key = option + "=";
            if (tok.rfind(key, 0) == 0 && tok.size() > key.size())
            {
                return string(tok.substr(key.size()));
            }
        }

        return string("");
    }

    // Binary header (little-endian)
#pragma pack(push, 1)
    struct HeaderV1
    {
        char magic[8];        // "ECMIOv1\0"
        uint32_t fileType;    // 1=input, 2=output
        uint32_t version;     // 1
        uint32_t N;           // number of records
        double time;
        double deltaT;
        uint32_t keyMode;     // 0=globalCellId, 1=localCellId
        uint32_t nInputs;     // number of scalar inputs following
    };

    struct HeaderV2
    {
        char magic[8];        // "ECMIOv1\0"
        uint32_t fileType;    // 1=input, 2=output
        uint32_t version;     // 2
        uint32_t N;           // number of records
        double time;
        double deltaT;
        uint32_t keyMode;     // 0=globalCellId, 1=localCellId
        uint32_t nInputs;     // number of scalar inputs following
        uint64_t stepId;      // transaction step ID
    };

    struct LastGoodHeader
    {
        char magic[8];        // "ECMLAST\0"
        uint32_t version;     // 1
        uint64_t stepId;
        double time;
        double qSum;
        int32_t returnCode;
        uint32_t N;           // number of records
    };
#pragma pack(pop)

    static_assert(sizeof(HeaderV1) == 44, "HeaderV1 size must be 44 bytes");
    static_assert(sizeof(HeaderV2) == 52, "HeaderV2 size must be 52 bytes");
    static_assert(sizeof(LastGoodHeader) == 44, "LastGoodHeader size must be 44 bytes");

    struct HeaderInfo
    {
        uint32_t fileType = 0;
        uint32_t version = 0;
        uint32_t N = 0;
        double time = 0.0;
        double deltaT = 0.0;
        uint32_t keyMode = 0;
        uint32_t nInputs = 0;
        uint64_t stepId = 0;
    };

    struct RestartCheckpointState
    {
        fileName timeName;
        scalar timeValue = 0.0;
        uint64_t stepId = 0;
        uint64_t lastGoodStepId = 0;
        scalar lastGoodTime = 0.0;
        scalar lastGoodQSum = 0.0;
        label lastReturnCode = 0;
        label callStepCounter = 0;
        scalar accumulatedDt = 0.0;
        scalar alpha = 1.0;
        scalar lastTEff = 0.0;
        label missingOutputCount = 0;
        bool degradedMode = false;
        HashTable<scalar, label> qByKey;
    };

    inline bool isLittleEndian()
    {
        uint16_t x = 1;
        return *reinterpret_cast<uint8_t*>(&x) == 1;
    }

    inline void setMagic7(char magic[8])
    {
        const char* m = "ECMIOv1";
        std::memset(magic, 0, 8);
        std::memcpy(magic, m, 7);
    }

    inline bool checkMagic(const char magic[8])
    {
        return std::memcmp(magic, "ECMIOv1", 7) == 0;
    }

    inline void setLastGoodMagic(char magic[8])
    {
        const char* m = "ECMLAST";
        std::memset(magic, 0, 8);
        std::memcpy(magic, m, 7);
    }

    inline bool checkLastGoodMagic(const char magic[8])
    {
        return std::memcmp(magic, "ECMLAST", 7) == 0;
    }

    inline bool readHeader(std::istream& is, HeaderInfo& info)
    {
        HeaderV1 h1{};
        is.read(reinterpret_cast<char*>(&h1), sizeof(h1));
        if (!is.good() || !checkMagic(h1.magic))
        {
            return false;
        }

        info.fileType = h1.fileType;
        info.version = h1.version;
        info.N = h1.N;
        info.time = h1.time;
        info.deltaT = h1.deltaT;
        info.keyMode = h1.keyMode;
        info.nInputs = h1.nInputs;
        info.stepId = 0;

        if (h1.version >= 2u)
        {
            uint64_t stepId = 0;
            is.read(reinterpret_cast<char*>(&stepId), sizeof(stepId));
            if (!is.good())
            {
                return false;
            }
            info.stepId = stepId;
        }

        return true;
    }

    inline bool writeHeaderV2(std::ostream& os, const HeaderInfo& info)
    {
        HeaderV2 h{};
        setMagic7(h.magic);
        h.fileType = info.fileType;
        h.version = 2u;
        h.N = info.N;
        h.time = info.time;
        h.deltaT = info.deltaT;
        h.keyMode = info.keyMode;
        h.nInputs = info.nInputs;
        h.stepId = info.stepId;
        os.write(reinterpret_cast<const char*>(&h), sizeof(h));
        return os.good();
    }

    inline bool parseCheckpointTimeName(const std::string& name, scalar& timeValue)
    {
        if (name.empty())
        {
            return false;
        }

        char* endPtr = nullptr;
        const double parsed = std::strtod(name.c_str(), &endPtr);
        if (endPtr == name.c_str() || *endPtr != '\0')
        {
            return false;
        }

        timeValue = static_cast<scalar>(parsed);
        return true;
    }

    bool readRestartCheckpointStateFile
    (
        const fileName& stateFile,
        RestartCheckpointState& state
    )
    {
        std::ifstream is(stateFile.c_str());
        if (!is.good())
        {
            return false;
        }

        std::string key;
        int version = 0;
        label qCount = 0;

        if (!(is >> key >> version) || key != "version" || version != 1)
        {
            return false;
        }

        auto readScalarEntry = [&](const char* expected, auto& value) -> bool
        {
            std::string entry;
            return (is >> entry >> value) && entry == expected;
        };

        unsigned long long stepIdValue = 0;
        unsigned long long lastGoodStepIdValue = 0;
        int degradedModeInt = 0;

        if
        (
            !readScalarEntry("stepId", stepIdValue)
         || !readScalarEntry("lastGoodStepId", lastGoodStepIdValue)
         || !readScalarEntry("lastGoodTime", state.lastGoodTime)
         || !readScalarEntry("lastGoodQSum", state.lastGoodQSum)
         || !readScalarEntry("lastReturnCode", state.lastReturnCode)
         || !readScalarEntry("callStepCounter", state.callStepCounter)
         || !readScalarEntry("accumulatedDt", state.accumulatedDt)
         || !readScalarEntry("alpha", state.alpha)
         || !readScalarEntry("lastTEff", state.lastTEff)
         || !readScalarEntry("missingOutputCount", state.missingOutputCount)
         || !readScalarEntry("degradedMode", degradedModeInt)
         || !readScalarEntry("qByKeyCount", qCount)
        )
        {
            return false;
        }

        state.stepId = static_cast<uint64_t>(stepIdValue);
        state.lastGoodStepId = static_cast<uint64_t>(lastGoodStepIdValue);
        state.degradedMode = (degradedModeInt != 0);
        state.qByKey.clear();

        for (label i = 0; i < qCount; ++i)
        {
            label k = 0;
            scalar q = 0.0;
            if (!(is >> k >> q))
            {
                state.qByKey.clear();
                return false;
            }
            state.qByKey.insert(k, q);
        }

        return true;
    }

    inline fileName tmpName(const fileName& f)
    {
        return f + ".tmp";
    }

    inline std::string trimCopy(const std::string& in)
    {
        size_t start = 0;
        while (start < in.size() && std::isspace(static_cast<unsigned char>(in[start]))) { start++; }
        size_t end = in.size();
        while (end > start && std::isspace(static_cast<unsigned char>(in[end - 1]))) { end--; }
        return in.substr(start, end - start);
    }

    inline std::string stripQuotes(const std::string& s)
    {
        if (s.size() >= 2 && s.front() == '"' && s.back() == '"')
        {
            return s.substr(1, s.size() - 2);
        }
        return s;
    }

    inline std::vector<std::string> splitCsvLine(const std::string& line)
    {
        std::vector<std::string> out;
        std::string token;
        std::istringstream iss(line);
        while (std::getline(iss, token, ','))
        {
            out.push_back(stripQuotes(trimCopy(token)));
        }
        return out;
    }

    inline bool extractJsonString(const std::string& text, const std::string& key, std::string& value)
    {
        const std::string needle = "\"" + key + "\"";
        size_t pos = text.find(needle);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos = text.find(':', pos);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos++;
        while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos])))
        {
            pos++;
        }
        if (pos >= text.size() || text[pos] != '\"')
        {
            return false;
        }
        size_t end = text.find('\"', pos + 1);
        if (end == std::string::npos)
        {
            return false;
        }
        value = text.substr(pos + 1, end - pos - 1);
        return true;
    }

    inline bool extractJsonNumber(const std::string& text, const std::string& key, double& value)
    {
        const std::string needle = "\"" + key + "\"";
        size_t pos = text.find(needle);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos = text.find(':', pos);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos++;
        while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos])))
        {
            pos++;
        }
        if (pos >= text.size())
        {
            return false;
        }
        const char* start = text.c_str() + pos;
        char* endPtr = nullptr;
        const double v = std::strtod(start, &endPtr);
        if (endPtr == start)
        {
            return false;
        }
        value = v;
        return true;
    }

    inline bool extractJsonArray(const std::string& text, const std::string& key, std::string& value)
    {
        const std::string needle = "\"" + key + "\"";
        size_t pos = text.find(needle);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos = text.find(':', pos);
        if (pos == std::string::npos)
        {
            return false;
        }
        pos = text.find('[', pos);
        if (pos == std::string::npos)
        {
            return false;
        }

        size_t end = pos;
        int depth = 0;
        for (; end < text.size(); ++end)
        {
            if (text[end] == '[')
            {
                depth++;
            }
            else if (text[end] == ']')
            {
                depth--;
                if (depth == 0)
                {
                    value = text.substr(pos, end - pos + 1);
                    return true;
                }
            }
        }

        return false;
    }

    inline bool parseJsonRecordPairs(const std::string& arrayText, HashTable<scalar, label>& qByKey)
    {
        qByKey.clear();
        const char* p = arrayText.c_str();
        char* endPtr = nullptr;

        auto skipSpace = [&]()
        {
            while (*p && std::isspace(static_cast<unsigned char>(*p)))
            {
                ++p;
            }
        };

        skipSpace();
        if (*p != '[')
        {
            return false;
        }
        ++p;

        while (*p)
        {
            skipSpace();
            if (*p == ']')
            {
                return true;
            }
            if (*p == ',')
            {
                ++p;
                continue;
            }
            if (*p != '[')
            {
                return false;
            }
            ++p;

            skipSpace();
            const long key = std::strtol(p, &endPtr, 10);
            if (endPtr == p)
            {
                return false;
            }
            p = endPtr;

            skipSpace();
            if (*p != ',')
            {
                return false;
            }
            ++p;

            skipSpace();
            const double qVal = std::strtod(p, &endPtr);
            if (endPtr == p)
            {
                return false;
            }
            p = endPtr;

            skipSpace();
            if (*p != ']')
            {
                return false;
            }
            ++p;

            qByKey.insert(static_cast<label>(key), static_cast<scalar>(qVal));
        }

        return false;
    }
}


void ecmCoupler::loadElementMapping()
{
    hasElementMapping_ = false;
    cellToEcmElement_.clear();
    nEcmElements_ = 0;

    // Use std::vector for O(N) loading (List<label>::append is O(N^2))
    std::vector<int> rawKeys, rawVals;
    label n = 0;
    bool readOk = false;

    if (Pstream::master() || !Pstream::parRun())
    {
        std::ifstream fin(elementMappingFile_.c_str());
        if (!fin.good())
        {
            WarningInFunction
                << "Cannot open elementMappingFile: " << elementMappingFile_ << nl;
        }
        else
        {
            rawKeys.reserve(1100000);
            rawVals.reserve(1100000);

            std::string line;
            std::getline(fin, line); // skip header

            label maxEcmId = -1;
            while (std::getline(fin, line))
            {
                if (line.empty()) continue;
                std::istringstream ss(line);
                std::string tok;
                int meshKey = -1, ecmCellId = -1;
                if (std::getline(ss, tok, ','))
                {
                    try { meshKey = std::stoi(tok); } catch (...) { continue; }
                }
                if (std::getline(ss, tok, ','))
                {
                    try { ecmCellId = std::stoi(tok); } catch (...) { continue; }
                }
                if (meshKey >= 0 && ecmCellId >= 0)
                {
                    rawKeys.push_back(meshKey);
                    rawVals.push_back(ecmCellId);
                    if (ecmCellId > maxEcmId) maxEcmId = ecmCellId;
                }
            }

            nEcmElements_ = (maxEcmId >= 0) ? maxEcmId + 1 : 0;
            n = static_cast<label>(rawKeys.size());
            readOk = (n > 0);
            Info<< "ECM element mapping loaded: " << n
                << " cells -> " << nEcmElements_ << " elements from "
                << elementMappingFile_ << nl;
        }
    }

    if (Pstream::parRun())
    {
        // Broadcast size + raw int arrays via MPI (contiguous, fast)
        Pstream::broadcast(n);
        Pstream::broadcast(nEcmElements_);

        if (!Pstream::master())
        {
            rawKeys.resize(static_cast<size_t>(n));
            rawVals.resize(static_cast<size_t>(n));
        }

        if (n > 0)
        {
            // Use List<label> wrapper for broadcastList
            // Build on master, broadcast to workers
            List<label> kL(n), vL(n);
            if (Pstream::master())
            {
                for (label i = 0; i < n; i++)
                {
                    kL[i] = static_cast<label>(rawKeys[static_cast<size_t>(i)]);
                    vL[i] = static_cast<label>(rawVals[static_cast<size_t>(i)]);
                }
            }
            Pstream::broadcastList(kL);
            Pstream::broadcastList(vL);

            // Build hash map on all ranks
            cellToEcmElement_.reserve(static_cast<size_t>(n));
            forAll(kL, i)
            {
                cellToEcmElement_[kL[i]] = vL[i];
            }
        }
    }
    else
    {
        if (!readOk) return;

        cellToEcmElement_.reserve(static_cast<size_t>(n));
        for (label i = 0; i < n; i++)
        {
            cellToEcmElement_[rawKeys[static_cast<size_t>(i)]] =
                rawVals[static_cast<size_t>(i)];
        }
    }

    hasElementMapping_ = (nEcmElements_ > 0 && !cellToEcmElement_.empty());
}


// * * * * * * * * * * * * * * * Constructors  * * * * * * * * * * * * * * //

ecmCoupler::ecmCoupler(const word& name, const Time& runTime, const dictionary& dict)
:
    fvMeshFunctionObject(name, runTime, dict),
    dict_(dict),

    zoneName_(dict.lookupOrDefault<word>("zone", "activeZone")),
    TName_(dict.lookupOrDefault<word>("T", "T")),

    qFieldName_(dict.lookupOrDefault<word>("qField", "ecmQdot")),
    stFieldName_(dict.lookupOrDefault<word>("stField", "ecmST")),

    couplingMode_(dict.lookupOrDefault<word>("couplingMode", "elementWise")),
    lumpedOutput_(dict.lookupOrDefault<word>("lumpedOutput", "totalPower")),
    totalVolumeScale_(dict.lookupOrDefault<scalar>("totalVolumeScale", 1.0)),

    outputMode_(dict.lookupOrDefault<word>("outputMode", "volumetricHeat")),
    rhoCp_(dict.lookupOrDefault<scalar>("rhoCp", 0.0)),
    tEffMode_(dict.lookupOrDefault<word>("tEffMode", "volumeAverage")),
    sensorZoneName_(dict.lookupOrDefault<word>("sensorZone", "")),
    coreAxis_(dict.lookupOrDefault<vector>("coreAxis", vector(0, 0, 1))),
    coreOrigin_(dict.lookupOrDefault<vector>("coreOrigin", vector(0, 0, 0))),
    axialProfile_(dict.lookupOrDefault<word>("axialProfile", "uniform")),
    axialAxis_(dict.lookupOrDefault<vector>("axialAxis", vector(0, 0, 1))),
    axialOrigin_(dict.lookupOrDefault<vector>("axialOrigin", vector(0, 0, 0))),
    axialBias_(dict.lookupOrDefault<scalar>("axialBias", 0.0)),

    inFile_(dict.lookupOrDefault<fileName>("inFile", "ecm_in.bin")),
    outFile_(dict.lookupOrDefault<fileName>("outFile", "ecm_out.bin")),
    lastGoodFile_(dict.lookupOrDefault<fileName>("lastGoodFile", "artifacts/runtime/ecm_last_good.bin")),
    ioMode_(dict.lookupOrDefault<word>("ioMode", "binary")),
    parallelMode_(dict.lookupOrDefault<word>("parallelMode", "serialOnly")),
    keyMode_(dict.lookupOrDefault<word>("keyMode", "globalCellId")),

    relaxAlpha_(dict.lookupOrDefault<scalar>("relaxation", 1.0)),
    writeFields_(dict.lookupOrDefault<Switch>("writeFields", true)),
    adaptiveRelaxation_(dict.lookupOrDefault<Switch>("adaptiveRelaxation", false)),
    alphaMin_(dict.lookupOrDefault<scalar>("alphaMin", 0.1)),
    alphaMax_(dict.lookupOrDefault<scalar>("alphaMax", 1.0)),
    alphaIncrease_(dict.lookupOrDefault<scalar>("alphaIncrease", 0.05)),
    alphaDecrease_(dict.lookupOrDefault<scalar>("alphaDecrease", 0.2)),
    deltaQThreshold_(dict.lookupOrDefault<scalar>("deltaQThreshold", 0.0)),
    deltaTThreshold_(dict.lookupOrDefault<scalar>("deltaTThreshold", 0.0)),
    alpha_(relaxAlpha_),
    lastTEff_(0.0),
    missingOutputAction_(dict.lookupOrDefault<word>("missingOutputAction", "warn")),
    missingOutputLimit_(dict.lookupOrDefault<label>("missingOutputLimit", 0)),
    missingOutputCount_(0),
    degradedMode_(false),
    subIterations_(dict.lookupOrDefault<label>("subIterations", 1)),
    subIterationResult_(dict.lookupOrDefault<word>("subIterationResult", "average")),
    temporalInterpolation_(dict.lookupOrDefault<word>("temporalInterpolation", "hold")),

    command_(dict.lookupOrDefault<string>("command", "python3 ../../python/ecm_coupler.py")),
    wrapperCommand_(dict.lookupOrDefault<string>("wrapperCommand", command_)),

    wrapperMode_(dict.lookupOrDefault<word>("wrapperMode", "single")),
    wrapperTempMode_(dict.lookupOrDefault<word>("wrapperTempMode", "coupled")),
    wrapperTempProfile_(dict.lookupOrDefault<word>("wrapperTempProfile", "constant")),
    wrapperCurrentProfile_(dict.lookupOrDefault<word>("wrapperCurrentProfile", "constant")),
    wrapperSteps_(dict.lookupOrDefault<label>("wrapperSteps", 1)),
    wrapperCsvPrefix_(dict.lookupOrDefault<fileName>("wrapperCsvPrefix", "ecm/ecm_wrapper")),
    wrapperCsvFile_(dict.lookupOrDefault<fileName>("wrapperCsvFile", "")),
    wrapperWriteCsv_(dict.lookupOrDefault<Switch>("wrapperWriteCsv", true)),
    wrapperExtraArgs_(dict.lookupOrDefault<string>("wrapperExtraArgs", "")),
    wrapperTempOffsetC_(dict.lookupOrDefault<scalar>("wrapperTempOffsetC", -273.15)),
    wrapperHeatColumn_(dict.lookupOrDefault<word>("wrapperHeatColumn", "Q_GEN_W")),
    wrapperQAhColumn_(dict.lookupOrDefault<word>("wrapperQAhColumn", "q_ah_next")),
    wrapperVrc1Column_(dict.lookupOrDefault<word>("wrapperVrc1Column", "V_RC_1")),
    wrapperVrc2Column_(dict.lookupOrDefault<word>("wrapperVrc2Column", "V_RC_2")),
    wrapperHysteresisColumn_(dict.lookupOrDefault<word>("wrapperHysteresisColumn", "H")),
    wrapperVoltageColumn_(dict.lookupOrDefault<word>("wrapperVoltageColumn", "V_T_V")),
    currentA_(dict.lookupOrDefault<scalar>("currentA", 0.0)),
    currentSign_(dict.lookupOrDefault<scalar>("currentSign", 1.0)),
    qAh_(dict.lookupOrDefault<scalar>("qAhInit", 0.0)),
    vRc1_(dict.lookupOrDefault<scalar>("vRc1Init", 0.0)),
    vRc2_(dict.lookupOrDefault<scalar>("vRc2Init", 0.0)),
    hysteresis_(dict.lookupOrDefault<scalar>("hysteresisInit", 0.0)),
    wrapperStateReset_(dict.lookupOrDefault<Switch>("wrapperStateReset", false)),
    wrapperStateFile_(dict.lookupOrDefault<fileName>("wrapperStateFile", "")),
    checkpointDir_(dict.lookupOrDefault<fileName>("checkpointDir", "")),
    writeTimeHistoryFile_(dict.lookupOrDefault<fileName>("writeTimeHistoryFile", "")),
    heatBalanceHistoryFile_(dict.lookupOrDefault<fileName>("heatBalanceHistoryFile", "")),

    inputMode_(dict.lookupOrDefault<word>("electricalInputsMode", "constant")),
    inputFile_(dict.lookupOrDefault<fileName>("electricalInputsFile", "")),
    inputTimeColumn_(dict.lookupOrDefault<word>("electricalInputsTimeColumn", "time")),
    inputTimes_(),
    inputSeries_(),
    inputSeriesLoaded_(false),
    inputNames_(),
    inputValues_(),
    stepId_(0),
    lastGoodStepId_(0),
    lastGoodTime_(0.0),
    lastGoodQSum_(0.0),
    lastReturnCode_(0),
    lastGoodQByKey_(),
    persistentPid_(-1),
    persistentStdinFd_(-1),
    persistentStdoutFd_(-1),

    elementMappingFile_(dict.lookupOrDefault<fileName>("elementMappingFile", "")),
    hasElementMapping_(false),
    cellToEcmElement_(),
    nEcmElements_(0),

    callEveryNSteps_(dict.lookupOrDefault<label>("callEveryNSteps", 1)),
    callStepCounter_(0),
    accumulatedDt_(0.0),
    restartCheckpointRestored_(false),
    restartCheckpointReconstructed_(false),
    restartReconstructionInfo_("")
{
    if (!isLittleEndian())
    {
        WarningInFunction
            << "This implementation assumes little-endian host. "
            << "You are running big-endian; binary IO will be incorrect." << nl;
    }
    if (mag(currentSign_) < SMALL)
    {
        WarningInFunction
            << "currentSign is zero; effective current sent to wrapper will be 0 A." << nl;
    }

    if (!dict.found("callEveryNSteps"))
    {
        const label inferred = parseCallEveryNStepsFromCommand(command_, callEveryNSteps_);
        if (inferred != callEveryNSteps_)
        {
            callEveryNSteps_ = inferred;
            Info<< "Inferred callEveryNSteps=" << callEveryNSteps_
                << " from wrapper command option --ecm-call-every-n-steps." << nl;
        }
    }

    readElectricalInputs(dict_);
    if (inputMode_ == "csv")
    {
        inputSeriesLoaded_ = loadElectricalInputsCsv();
        if (inputSeriesLoaded_)
        {
            updateElectricalInputsFromCsv(mesh_.time().value());
        }
    }
    ensureFields();

    if (elementMappingFile_.size())
    {
        loadElementMapping();
    }

    updateDerivedFilePaths();

    const bool restoredStartupState = restoreRestartCheckpoint();
    const bool loadedLastGood = (!restoredStartupState && readLastGoodSnapshot());

    if (restartCheckpointRestored_ && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< "Restored ECM restart checkpoint for time "
            << mesh_.time().timeName() << " from "
            << checkpointPathForTime(mesh_.time().timeName()) << nl;
    }
    else if (restartCheckpointReconstructed_ && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< restartReconstructionInfo_.c_str() << nl;
    }
    else if (loadedLastGood && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< "Loaded last-good ECM snapshot from " << lastGoodFile_
            << " (stepId=" << lastGoodStepId_ << ")." << nl;
    }

    initializeStartupFields();

    if (!restartCheckpointRestored_ && callEveryNSteps_ > 1)
    {
        callStepCounter_ = callEveryNSteps_ - 1;
        if (Pstream::master() || !Pstream::parRun())
        {
            Info<< "No exact restart checkpoint at time " << mesh_.time().timeName()
                << "; forcing immediate ECM call on first execute." << nl;
        }
    }
}


ecmCoupler::~ecmCoupler()
{
    stopPersistentWrapper();
}


// * * * * * * * * * * * * * * * Member Functions  * * * * * * * * * * * * //

bool ecmCoupler::read(const dictionary& dict)
{
    dict_ = dict;

    zoneName_     = dict_.lookupOrDefault<word>("zone", zoneName_);
    TName_        = dict_.lookupOrDefault<word>("T", TName_);

    qFieldName_   = dict_.lookupOrDefault<word>("qField", qFieldName_);
    stFieldName_  = dict_.lookupOrDefault<word>("stField", stFieldName_);

    couplingMode_ = dict_.lookupOrDefault<word>("couplingMode", couplingMode_);
    lumpedOutput_ = dict_.lookupOrDefault<word>("lumpedOutput", lumpedOutput_);
    totalVolumeScale_ = dict_.lookupOrDefault<scalar>("totalVolumeScale", totalVolumeScale_);

    outputMode_   = dict_.lookupOrDefault<word>("outputMode", outputMode_);
    rhoCp_        = dict_.lookupOrDefault<scalar>("rhoCp", rhoCp_);
    tEffMode_     = dict_.lookupOrDefault<word>("tEffMode", tEffMode_);
    sensorZoneName_ = dict_.lookupOrDefault<word>("sensorZone", sensorZoneName_);
    coreAxis_     = dict_.lookupOrDefault<vector>("coreAxis", coreAxis_);
    coreOrigin_   = dict_.lookupOrDefault<vector>("coreOrigin", coreOrigin_);
    axialProfile_ = dict_.lookupOrDefault<word>("axialProfile", axialProfile_);
    axialAxis_    = dict_.lookupOrDefault<vector>("axialAxis", axialAxis_);
    axialOrigin_  = dict_.lookupOrDefault<vector>("axialOrigin", axialOrigin_);
    axialBias_    = dict_.lookupOrDefault<scalar>("axialBias", axialBias_);

    inFile_       = dict_.lookupOrDefault<fileName>("inFile", inFile_);
    outFile_      = dict_.lookupOrDefault<fileName>("outFile", outFile_);
    lastGoodFile_ = dict_.lookupOrDefault<fileName>("lastGoodFile", lastGoodFile_);
    ioMode_       = dict_.lookupOrDefault<word>("ioMode", ioMode_);
    parallelMode_ = dict_.lookupOrDefault<word>("parallelMode", parallelMode_);
    keyMode_      = dict_.lookupOrDefault<word>("keyMode", keyMode_);

    relaxAlpha_   = dict_.lookupOrDefault<scalar>("relaxation", relaxAlpha_);
    writeFields_  = dict_.lookupOrDefault<Switch>("writeFields", writeFields_);
    adaptiveRelaxation_ = dict_.lookupOrDefault<Switch>("adaptiveRelaxation", adaptiveRelaxation_);
    alphaMin_     = dict_.lookupOrDefault<scalar>("alphaMin", alphaMin_);
    alphaMax_     = dict_.lookupOrDefault<scalar>("alphaMax", alphaMax_);
    alphaIncrease_ = dict_.lookupOrDefault<scalar>("alphaIncrease", alphaIncrease_);
    alphaDecrease_ = dict_.lookupOrDefault<scalar>("alphaDecrease", alphaDecrease_);
    deltaQThreshold_ = dict_.lookupOrDefault<scalar>("deltaQThreshold", deltaQThreshold_);
    deltaTThreshold_ = dict_.lookupOrDefault<scalar>("deltaTThreshold", deltaTThreshold_);
    alpha_ = relaxAlpha_;
    missingOutputAction_ = dict_.lookupOrDefault<word>("missingOutputAction", missingOutputAction_);
    missingOutputLimit_ = dict_.lookupOrDefault<label>("missingOutputLimit", missingOutputLimit_);
    subIterations_ = dict_.lookupOrDefault<label>("subIterations", subIterations_);
    subIterationResult_ = dict_.lookupOrDefault<word>("subIterationResult", subIterationResult_);
    temporalInterpolation_ = dict_.lookupOrDefault<word>("temporalInterpolation", temporalInterpolation_);

    command_      = dict_.lookupOrDefault<string>("command", command_);
    wrapperCommand_ = dict_.lookupOrDefault<string>("wrapperCommand", command_);
    elementMappingFile_ = dict_.lookupOrDefault<fileName>("elementMappingFile", elementMappingFile_);
    callEveryNSteps_    = dict_.lookupOrDefault<label>("callEveryNSteps", callEveryNSteps_);
    if (!dict_.found("callEveryNSteps"))
    {
        const label inferred = parseCallEveryNStepsFromCommand(command_, callEveryNSteps_);
        if (inferred != callEveryNSteps_)
        {
            callEveryNSteps_ = inferred;
            if (Pstream::master() || !Pstream::parRun())
            {
                Info<< "Inferred callEveryNSteps=" << callEveryNSteps_
                    << " from wrapper command option --ecm-call-every-n-steps." << nl;
            }
        }
    }
    if (mag(currentSign_) < SMALL)
    {
        WarningInFunction
            << "currentSign is zero; effective current sent to wrapper will be 0 A." << nl;
    }

    wrapperMode_         = dict_.lookupOrDefault<word>("wrapperMode", wrapperMode_);
    wrapperTempMode_     = dict_.lookupOrDefault<word>("wrapperTempMode", wrapperTempMode_);
    wrapperTempProfile_  = dict_.lookupOrDefault<word>("wrapperTempProfile", wrapperTempProfile_);
    wrapperCurrentProfile_ = dict_.lookupOrDefault<word>("wrapperCurrentProfile", wrapperCurrentProfile_);
    wrapperSteps_        = dict_.lookupOrDefault<label>("wrapperSteps", wrapperSteps_);
    wrapperCsvPrefix_    = dict_.lookupOrDefault<fileName>("wrapperCsvPrefix", wrapperCsvPrefix_);
    wrapperCsvFile_      = dict_.lookupOrDefault<fileName>("wrapperCsvFile", wrapperCsvFile_);
    wrapperWriteCsv_     = dict_.lookupOrDefault<Switch>("wrapperWriteCsv", wrapperWriteCsv_);
    wrapperExtraArgs_    = dict_.lookupOrDefault<string>("wrapperExtraArgs", wrapperExtraArgs_);
    wrapperTempOffsetC_  = dict_.lookupOrDefault<scalar>("wrapperTempOffsetC", wrapperTempOffsetC_);
    wrapperHeatColumn_   = dict_.lookupOrDefault<word>("wrapperHeatColumn", wrapperHeatColumn_);
    wrapperQAhColumn_    = dict_.lookupOrDefault<word>("wrapperQAhColumn", wrapperQAhColumn_);
    wrapperVrc1Column_   = dict_.lookupOrDefault<word>("wrapperVrc1Column", wrapperVrc1Column_);
    wrapperVrc2Column_   = dict_.lookupOrDefault<word>("wrapperVrc2Column", wrapperVrc2Column_);
    wrapperHysteresisColumn_ = dict_.lookupOrDefault<word>("wrapperHysteresisColumn", wrapperHysteresisColumn_);
    wrapperVoltageColumn_ = dict_.lookupOrDefault<word>("wrapperVoltageColumn", wrapperVoltageColumn_);
    currentA_            = dict_.lookupOrDefault<scalar>("currentA", currentA_);
    currentSign_         = dict_.lookupOrDefault<scalar>("currentSign", currentSign_);
    qAh_                 = dict_.lookupOrDefault<scalar>("qAhInit", qAh_);
    vRc1_                = dict_.lookupOrDefault<scalar>("vRc1Init", vRc1_);
    vRc2_                = dict_.lookupOrDefault<scalar>("vRc2Init", vRc2_);
    hysteresis_          = dict_.lookupOrDefault<scalar>("hysteresisInit", hysteresis_);
    wrapperStateReset_   = dict_.lookupOrDefault<Switch>("wrapperStateReset", wrapperStateReset_);
    wrapperStateFile_    = dict_.lookupOrDefault<fileName>("wrapperStateFile", wrapperStateFile_);
    checkpointDir_       = dict_.lookupOrDefault<fileName>("checkpointDir", checkpointDir_);
    writeTimeHistoryFile_ = dict_.lookupOrDefault<fileName>("writeTimeHistoryFile", writeTimeHistoryFile_);
    heatBalanceHistoryFile_ = dict_.lookupOrDefault<fileName>("heatBalanceHistoryFile", heatBalanceHistoryFile_);

    inputMode_           = dict_.lookupOrDefault<word>("electricalInputsMode", inputMode_);
    inputFile_           = dict_.lookupOrDefault<fileName>("electricalInputsFile", inputFile_);
    inputTimeColumn_     = dict_.lookupOrDefault<word>("electricalInputsTimeColumn", inputTimeColumn_);

    updateDerivedFilePaths();

    readElectricalInputs(dict_);
    if (inputMode_ == "csv")
    {
        inputSeriesLoaded_ = loadElectricalInputsCsv();
        if (inputSeriesLoaded_)
        {
            updateElectricalInputsFromCsv(mesh_.time().value());
        }
    }
    ensureFields();

    return true;
}


void ecmCoupler::updateDerivedFilePaths()
{
    if (wrapperStateFile_.empty())
    {
        wrapperStateFile_ = parseOptionValueFromCommand(command_, "--state");
    }

    if (checkpointDir_.empty())
    {
        if (!lastGoodFile_.empty() && !lastGoodFile_.path().empty())
        {
            checkpointDir_ = lastGoodFile_.path()/"restartCheckpoints";
        }
        else
        {
            checkpointDir_ = "ecm/restartCheckpoints";
        }
    }

    if (writeTimeHistoryFile_.empty())
    {
        fileName historyDir("ecm");
        if (!checkpointDir_.empty() && !checkpointDir_.path().empty())
        {
            historyDir = checkpointDir_.path();
        }
        writeTimeHistoryFile_ = historyDir/"writeTimeHistory.json";
    }

    if (heatBalanceHistoryFile_.empty())
    {
        fileName historyDir("ecm");
        if (!checkpointDir_.empty() && !checkpointDir_.path().empty())
        {
            historyDir = checkpointDir_.path();
        }
        heatBalanceHistoryFile_ = historyDir/"heatBalanceHistory.csv";
    }
}


fileName ecmCoupler::checkpointPathForTime(const fileName& timeName) const
{
    return checkpointDir_/timeName;
}


bool ecmCoupler::copyFileContents(const fileName& src, const fileName& dst)
{
    std::ifstream is(src.c_str(), std::ios::binary);
    if (!is.good())
    {
        return false;
    }

    if (!dst.path().empty())
    {
        mkDir(dst.path());
    }

    std::ofstream os(dst.c_str(), std::ios::binary | std::ios::trunc);
    if (!os.good())
    {
        return false;
    }

    os << is.rdbuf();
    os.flush();

    return is.good() && os.good();
}


bool ecmCoupler::writeRestartCheckpoint() const
{
    if (checkpointDir_.empty())
    {
        return false;
    }

    if (Pstream::parRun() && !Pstream::master())
    {
        return true;
    }

    const fileName dir = checkpointPathForTime(mesh_.time().timeName());
    if (!checkpointDir_.empty())
    {
        mkDir(checkpointDir_);
    }
    mkDir(dir);

    const fileName stateFile = dir/"coupler_state.dat";
    std::ofstream os(stateFile.c_str(), std::ios::trunc);
    if (!os.good())
    {
        WarningInFunction << "Failed to open restart checkpoint file " << stateFile << nl;
        return false;
    }

    os << std::setprecision(17);
    os << "version 1\n";
    os << "stepId " << stepId_ << "\n";
    os << "lastGoodStepId " << lastGoodStepId_ << "\n";
    os << "lastGoodTime " << lastGoodTime_ << "\n";
    os << "lastGoodQSum " << lastGoodQSum_ << "\n";
    os << "lastReturnCode " << lastReturnCode_ << "\n";
    os << "callStepCounter " << callStepCounter_ << "\n";
    os << "accumulatedDt " << accumulatedDt_ << "\n";
    os << "alpha " << alpha_ << "\n";
    os << "lastTEff " << lastTEff_ << "\n";
    os << "missingOutputCount " << missingOutputCount_ << "\n";
    os << "degradedMode " << (degradedMode_ ? 1 : 0) << "\n";
    os << "qByKeyCount " << lastGoodQByKey_.size() << "\n";
    typedef HashTable<scalar, label> QTable;
    forAllConstIter(QTable, lastGoodQByKey_, iter)
    {
        os << iter.key() << " " << iter() << "\n";
    }

    os.flush();
    if (!os.good())
    {
        WarningInFunction << "Failed to write restart checkpoint file " << stateFile << nl;
        return false;
    }

    if (!wrapperStateFile_.empty())
    {
        const fileName wrapperCheckpoint = dir/"wrapper_state.json";
        if (isFile(wrapperStateFile_) && !copyFileContents(wrapperStateFile_, wrapperCheckpoint))
        {
            WarningInFunction
                << "Failed to copy wrapper state file " << wrapperStateFile_
                << " to restart checkpoint " << wrapperCheckpoint << nl;
        }
    }

    if (!lastGoodFile_.empty() && isFile(lastGoodFile_))
    {
        const fileName lastGoodCheckpoint = dir/"last_good.bin";
        if (!copyFileContents(lastGoodFile_, lastGoodCheckpoint))
        {
            WarningInFunction
                << "Failed to copy last-good snapshot " << lastGoodFile_
                << " to restart checkpoint " << lastGoodCheckpoint << nl;
        }
    }

    return true;
}


bool ecmCoupler::writeWriteTimeHistory() const
{
    if (writeTimeHistoryFile_.empty())
    {
        return false;
    }

    if (Pstream::parRun() && !Pstream::master())
    {
        return true;
    }

    fileName historyDir = writeTimeHistoryFile_.path();
    if (!historyDir.empty())
    {
        mkDir(historyDir);
    }

    const fileName tmpFile = tmpName(writeTimeHistoryFile_);
    std::ofstream os(tmpFile.c_str(), std::ios::trunc);
    if (!os.good())
    {
        WarningInFunction << "Failed to open writeTime history file " << tmpFile << nl;
        return false;
    }

    scalar previousTimeValue = -GREAT;
    fileName previousTimeName("");

    if (!checkpointDir_.empty())
    {
        DIR* dir = opendir(checkpointDir_.c_str());
        if (dir != nullptr)
        {
            const scalar currentTimeValue = mesh_.time().value();
            while (dirent* entry = readdir(dir))
            {
                const std::string name(entry->d_name);
                if (name == "." || name == "..")
                {
                    continue;
                }

                scalar timeValue = 0.0;
                if (!parseCheckpointTimeName(name, timeValue))
                {
                    continue;
                }

                if (name == mesh_.time().timeName())
                {
                    continue;
                }

                if (timeValue < currentTimeValue && timeValue > previousTimeValue)
                {
                    previousTimeValue = timeValue;
                    previousTimeName = fileName(name);
                }
            }
            closedir(dir);
        }
    }

    os << std::setprecision(17);
    os << "{\n";
    os << "  \"version\": 1,\n";
    os << "  \"currentWriteTime\": \"" << mesh_.time().timeName() << "\",\n";
    if (previousTimeName.empty())
    {
        os << "  \"previousWriteTime\": null,\n";
    }
    else
    {
        os << "  \"previousWriteTime\": \"" << previousTimeName << "\",\n";
    }
    os << "  \"stepId\": " << stepId_ << ",\n";
    os << "  \"lastGoodStepId\": " << lastGoodStepId_ << ",\n";
    os << "  \"lastGoodTime\": " << lastGoodTime_ << ",\n";
    os << "  \"lastGoodQSum\": " << lastGoodQSum_ << ",\n";
    os << "  \"callStepCounter\": " << callStepCounter_ << ",\n";
    os << "  \"accumulatedDt\": " << accumulatedDt_ << ",\n";
    os << "  \"alpha\": " << alpha_ << ",\n";
    os << "  \"lastTEff\": " << lastTEff_ << ",\n";
    os << "  \"qByKeyCount\": " << lastGoodQByKey_.size() << "\n";
    os << "}\n";

    os.flush();
    if (!os.good())
    {
        WarningInFunction << "Failed to write writeTime history file " << tmpFile << nl;
        return false;
    }

    if (std::rename(tmpFile.c_str(), writeTimeHistoryFile_.c_str()) != 0)
    {
        std::remove(tmpFile.c_str());
        WarningInFunction
            << "Failed to rename writeTime history file " << tmpFile
            << " to " << writeTimeHistoryFile_ << nl;
        return false;
    }

    return true;
}


bool ecmCoupler::appendHeatBalanceHistory
(
    const scalar timeValue,
    const scalar deltaT,
    const uint64_t outStepId,
    const scalar tEff,
    const scalar qRaw,
    const scalar qTarget,
    const scalar qApplied
) const
{
    if (heatBalanceHistoryFile_.empty())
    {
        return false;
    }

    if (Pstream::parRun() && !Pstream::master())
    {
        return true;
    }

    const fileName historyDir = heatBalanceHistoryFile_.path();
    if (!historyDir.empty())
    {
        mkDir(historyDir);
    }

    const bool needHeader = !isFile(heatBalanceHistoryFile_);
    std::ofstream os(heatBalanceHistoryFile_.c_str(), std::ios::app);
    if (!os.good())
    {
        WarningInFunction
            << "Failed to open heat-balance history file "
            << heatBalanceHistoryFile_ << nl;
        return false;
    }

    if (needHeader)
    {
        os << "time_s,delta_t_s,step_id,t_eff_k,alpha,q_raw_w,q_target_w,q_applied_w,source_sum_openfoam_w\n";
    }

    os << std::setprecision(17)
       << timeValue << ","
       << deltaT << ","
       << outStepId << ","
       << tEff << ","
       << alpha_ << ","
       << qRaw << ","
       << qTarget << ","
       << qApplied << ","
       << qApplied << "\n";
    os.flush();

    if (!os.good())
    {
        WarningInFunction
            << "Failed while writing heat-balance history file "
            << heatBalanceHistoryFile_ << nl;
        return false;
    }

    return true;
}


bool ecmCoupler::restoreRestartCheckpoint()
{
    restartCheckpointRestored_ = false;
    restartCheckpointReconstructed_ = false;
    restartReconstructionInfo_.clear();

    if (checkpointDir_.empty())
    {
        return false;
    }

    const fileName dir = checkpointPathForTime(mesh_.time().timeName());
    const fileName stateFile = dir/"coupler_state.dat";
    std::ifstream is(stateFile.c_str());
    if (!is.good())
    {
        return restoreRestartCheckpointFallback();
    }

    std::string key;
    int version = 0;
    label qCount = 0;

    if (!(is >> key >> version) || key != "version" || version != 1)
    {
        WarningInFunction << "Invalid restart checkpoint header in " << stateFile << nl;
        return false;
    }

    auto readScalarEntry = [&](const char* expected, auto& value) -> bool
    {
        std::string entry;
        if (!(is >> entry >> value) || entry != expected)
        {
            WarningInFunction
                << "Malformed restart checkpoint entry '" << expected
                << "' in " << stateFile << nl;
            return false;
        }
        return true;
    };

    unsigned long long stepIdValue = 0;
    unsigned long long lastGoodStepIdValue = 0;
    int degradedModeInt = 0;

    if
    (
        !readScalarEntry("stepId", stepIdValue)
     || !readScalarEntry("lastGoodStepId", lastGoodStepIdValue)
     || !readScalarEntry("lastGoodTime", lastGoodTime_)
     || !readScalarEntry("lastGoodQSum", lastGoodQSum_)
     || !readScalarEntry("lastReturnCode", lastReturnCode_)
     || !readScalarEntry("callStepCounter", callStepCounter_)
     || !readScalarEntry("accumulatedDt", accumulatedDt_)
     || !readScalarEntry("alpha", alpha_)
     || !readScalarEntry("lastTEff", lastTEff_)
     || !readScalarEntry("missingOutputCount", missingOutputCount_)
     || !readScalarEntry("degradedMode", degradedModeInt)
     || !readScalarEntry("qByKeyCount", qCount)
    )
    {
        return false;
    }

    stepId_ = static_cast<uint64_t>(stepIdValue);
    lastGoodStepId_ = static_cast<uint64_t>(lastGoodStepIdValue);
    degradedMode_ = (degradedModeInt != 0);
    lastGoodQByKey_.clear();

    for (label i = 0; i < qCount; ++i)
    {
        label k = 0;
        scalar q = 0.0;
        if (!(is >> k >> q))
        {
            WarningInFunction << "Truncated restart checkpoint qByKey data in " << stateFile << nl;
            lastGoodQByKey_.clear();
            return false;
        }
        lastGoodQByKey_.insert(k, q);
    }

    if (!wrapperStateFile_.empty())
    {
        const fileName wrapperCheckpoint = dir/"wrapper_state.json";
        if (isFile(wrapperCheckpoint))
        {
            if (!copyFileContents(wrapperCheckpoint, wrapperStateFile_))
            {
                WarningInFunction
                    << "Failed to restore wrapper state checkpoint " << wrapperCheckpoint
                    << " to " << wrapperStateFile_ << nl;
                return false;
            }
        }
    }

    if (!lastGoodFile_.empty())
    {
        const fileName lastGoodCheckpoint = dir/"last_good.bin";
        if (isFile(lastGoodCheckpoint) && !copyFileContents(lastGoodCheckpoint, lastGoodFile_))
        {
            WarningInFunction
                << "Failed to restore last-good checkpoint " << lastGoodCheckpoint
                << " to " << lastGoodFile_ << nl;
            return false;
        }
    }

    restartCheckpointRestored_ = true;
    return true;
}


bool ecmCoupler::restoreRestartCheckpointFallback()
{
    if (checkpointDir_.empty())
    {
        return false;
    }

    DIR* dirp = opendir(checkpointDir_.c_str());
    if (!dirp)
    {
        return false;
    }

    std::vector<RestartCheckpointState> states;
    for (dirent* entry = readdir(dirp); entry; entry = readdir(dirp))
    {
        const std::string name(entry->d_name);
        if (name == "." || name == "..")
        {
            continue;
        }

        scalar timeValue = 0.0;
        if (!parseCheckpointTimeName(name, timeValue))
        {
            continue;
        }

        RestartCheckpointState state;
        state.timeName = fileName(name);
        state.timeValue = timeValue;
        if (readRestartCheckpointStateFile(checkpointPathForTime(state.timeName)/"coupler_state.dat", state))
        {
            states.push_back(state);
        }
    }
    closedir(dirp);

    if (states.empty())
    {
        return false;
    }

    std::sort
    (
        states.begin(),
        states.end(),
        [](const RestartCheckpointState& a, const RestartCheckpointState& b)
        {
            return a.timeValue < b.timeValue;
        }
    );

    const scalar currentTime = mesh_.time().value();
    const RestartCheckpointState* lower = nullptr;
    const RestartCheckpointState* upper = nullptr;

    for (const RestartCheckpointState& state : states)
    {
        if (state.timeValue <= currentTime + SMALL)
        {
            lower = &state;
        }
        if (!upper && state.timeValue >= currentTime - SMALL)
        {
            upper = &state;
        }
    }

    if (lower && mag(lower->timeValue - currentTime) <= SMALL)
    {
        return false;
    }

    word temporalMode = temporalInterpolation_;
    if (temporalMode != "hold" && temporalMode != "linear")
    {
        temporalMode = "hold";
    }

    const RestartCheckpointState* base = nullptr;
    HashTable<scalar, label> reconstructedQ;
    scalar reconstructedTime = currentTime;
    scalar reconstructedQSum = 0.0;
    uint64_t reconstructedLastGoodStepId = 0;
    label reconstructedReturnCode = 0;
    std::ostringstream info;

    if
    (
        temporalMode == "linear"
     && lower
     && upper
     && upper->timeValue > lower->timeValue + SMALL
    )
    {
        const scalar weight =
            (currentTime - lower->timeValue)/(upper->timeValue - lower->timeValue);
        typedef HashTable<scalar, label> QTable;

        reconstructedQ = lower->qByKey;
        forAllConstIter(QTable, upper->qByKey, iterUpper)
        {
            const label key = iterUpper.key();
            const scalar qUpper = iterUpper();
            const auto iterLower = lower->qByKey.find(key);
            const scalar qLower = iterLower.found() ? iterLower() : qUpper;
            reconstructedQ.set(key, (1.0 - weight)*qLower + weight*qUpper);
        }

        reconstructedQSum =
            (1.0 - weight)*lower->lastGoodQSum + weight*upper->lastGoodQSum;
        reconstructedLastGoodStepId =
            max(lower->lastGoodStepId, upper->lastGoodStepId);
        reconstructedReturnCode =
            (upper->lastReturnCode != 0 ? upper->lastReturnCode : lower->lastReturnCode);
        base = lower;

        info << "Reconstructed ECM startup source for time " << mesh_.time().timeName()
             << " by linear interpolation between checkpoint times "
             << lower->timeName << " and " << upper->timeName << ".";
    }
    else if (lower || upper)
    {
        if (lower && upper)
        {
            const scalar lowerDist = mag(currentTime - lower->timeValue);
            const scalar upperDist = mag(upper->timeValue - currentTime);
            base = (upperDist < lowerDist ? upper : lower);
        }
        else
        {
            base = lower ? lower : upper;
        }

        reconstructedQ = base->qByKey;
        reconstructedTime = base->timeValue;
        reconstructedQSum = base->lastGoodQSum;
        reconstructedLastGoodStepId = base->lastGoodStepId;
        reconstructedReturnCode = base->lastReturnCode;

        info << "Reconstructed ECM startup source for time " << mesh_.time().timeName()
             << " from nearest checkpoint time " << base->timeName;
        if (base == upper)
        {
            info << " (future one-sided restore).";
        }
        else
        {
            info << " (hold restore).";
        }
    }
    else
    {
        return false;
    }

    if (reconstructedQ.empty())
    {
        return false;
    }

    lastGoodStepId_ = reconstructedLastGoodStepId;
    lastGoodTime_ = reconstructedTime;
    lastGoodQSum_ = reconstructedQSum;
    lastReturnCode_ = reconstructedReturnCode;
    lastGoodQByKey_ = reconstructedQ;

    stepId_ = 0;
    callStepCounter_ = 0;
    accumulatedDt_ = 0.0;
    alpha_ = relaxAlpha_;
    lastTEff_ = 0.0;
    missingOutputCount_ = 0;
    degradedMode_ = false;

    // Restore Python wrapper state and last-good snapshot from the base
    // checkpoint so the ECM backend sees a consistent time on its first call.
    // Without this, the active ecm_state.json retains whatever time it was
    // last written to (which may be ahead of the restart point), causing the
    // wrapper to detect a rewind and reset the battery state to initial
    // conditions.
    if (base != nullptr)
    {
        if (!wrapperStateFile_.empty())
        {
            const fileName wrapperCheckpoint =
                checkpointPathForTime(base->timeName)/"wrapper_state.json";
            if (isFile(wrapperCheckpoint))
            {
                if (!copyFileContents(wrapperCheckpoint, wrapperStateFile_))
                {
                    WarningInFunction
                        << "Failed to restore wrapper state from fallback "
                        << "checkpoint " << wrapperCheckpoint
                        << " to " << wrapperStateFile_ << nl;
                }
                else if (Pstream::master() || !Pstream::parRun())
                {
                    Info<< "Restored wrapper state from fallback checkpoint "
                        << base->timeName << " to " << wrapperStateFile_ << nl;
                }
            }
        }

        if (!lastGoodFile_.empty())
        {
            const fileName lastGoodCheckpoint =
                checkpointPathForTime(base->timeName)/"last_good.bin";
            if (isFile(lastGoodCheckpoint)
             && !copyFileContents(lastGoodCheckpoint, lastGoodFile_))
            {
                WarningInFunction
                    << "Failed to restore last-good from fallback checkpoint "
                    << lastGoodCheckpoint << " to " << lastGoodFile_ << nl;
            }
        }
    }

    restartCheckpointReconstructed_ = true;
    restartReconstructionInfo_ = info.str();
    return true;
}


void ecmCoupler::readElectricalInputs(const dictionary& d)
{
    inputNames_.clear();
    inputValues_.clear();

    if (!d.found("electricalInputs"))
    {
        return;
    }

    const dictionary& ei = d.subDict("electricalInputs");

    // Collect all entries as scalars
    forAllConstIter(dictionary, ei, iter)
    {
        const word& k = iter().keyword();
        if (ei.isDict(k))
        {
            continue;
        }

        scalar v = readScalar(ei.lookup(k));
        inputNames_.append(k);
        inputValues_.append(v);
    }
}

bool ecmCoupler::loadElectricalInputsCsv()
{
    inputTimes_.clear();
    inputSeries_.clear();

    if (inputFile_.empty())
    {
        WarningInFunction << "electricalInputsFile is empty; cannot load CSV inputs." << nl;
        return false;
    }

    std::ifstream is(inputFile_.c_str());
    if (!is.good())
    {
        WarningInFunction << "Failed to open electricalInputsFile: " << inputFile_ << nl;
        return false;
    }

    std::string headerLine;
    if (!std::getline(is, headerLine))
    {
        WarningInFunction << "electricalInputsFile missing header: " << inputFile_ << nl;
        return false;
    }

    const std::vector<std::string> headers = splitCsvLine(headerLine);
    if (headers.empty())
    {
        WarningInFunction << "electricalInputsFile has empty header: " << inputFile_ << nl;
        return false;
    }

    int timeIdx = -1;
    for (size_t i = 0; i < headers.size(); ++i)
    {
        if (headers[i] == inputTimeColumn_)
        {
            timeIdx = static_cast<int>(i);
            break;
        }
    }

    if (timeIdx < 0)
    {
        WarningInFunction
            << "electricalInputsFile missing time column '" << inputTimeColumn_
            << "': " << inputFile_ << nl;
        return false;
    }

    if (inputNames_.empty())
    {
        for (size_t i = 0; i < headers.size(); ++i)
        {
            if (static_cast<int>(i) == timeIdx)
            {
                continue;
            }
            inputNames_.append(word(headers[i]));
        }
    }

    if (inputNames_.empty())
    {
        WarningInFunction << "No electrical input columns specified or found in CSV." << nl;
        return false;
    }

    List<label> colIdx(inputNames_.size(), -1);
    forAll(inputNames_, i)
    {
        const word& name = inputNames_[i];
        for (size_t j = 0; j < headers.size(); ++j)
        {
            if (headers[j] == name)
            {
                colIdx[i] = static_cast<label>(j);
                break;
            }
        }
        if (colIdx[i] < 0)
        {
            WarningInFunction
                << "electricalInputsFile missing column '" << name
                << "'. Using previous/default value for this input." << nl;
        }
    }

    std::vector<scalar> timesVec;
    std::vector<std::vector<scalar>> seriesVec(inputNames_.size());

    std::string line;
    while (std::getline(is, line))
    {
        if (trimCopy(line).empty())
        {
            continue;
        }

        const std::vector<std::string> cols = splitCsvLine(line);
        if (static_cast<int>(cols.size()) <= timeIdx)
        {
            continue;
        }

        try
        {
            const scalar t = std::stod(cols[timeIdx]);
            if (!std::isfinite(t))
            {
                continue;
            }
            timesVec.push_back(t);

            forAll(inputNames_, i)
            {
                scalar v = (i < inputValues_.size()) ? inputValues_[i] : 0.0;
                const label idx = colIdx[i];
                if (idx >= 0 && idx < static_cast<label>(cols.size()))
                {
                    v = std::stod(cols[idx]);
                }
                seriesVec[i].push_back(v);
            }
        }
        catch (const std::exception&)
        {
            continue;
        }
    }

    if (timesVec.empty())
    {
        WarningInFunction << "electricalInputsFile has no data rows: " << inputFile_ << nl;
        return false;
    }

    inputTimes_.setSize(timesVec.size());
    for (size_t i = 0; i < timesVec.size(); ++i)
    {
        inputTimes_[i] = timesVec[i];
    }

    inputSeries_.setSize(inputNames_.size());
    inputValues_.setSize(inputNames_.size());
    forAll(inputNames_, i)
    {
        inputSeries_[i].setSize(timesVec.size());
        for (size_t j = 0; j < timesVec.size(); ++j)
        {
            inputSeries_[i][j] = seriesVec[i][j];
        }
        inputValues_[i] = inputSeries_[i][0];
    }

    return true;
}

bool ecmCoupler::updateElectricalInputsFromCsv(const scalar timeValue)
{
    if (!inputSeriesLoaded_ || inputTimes_.empty() || inputSeries_.empty())
    {
        return false;
    }

    const label n = inputTimes_.size();
    if (n == 1)
    {
        forAll(inputNames_, i)
        {
            inputValues_[i] = inputSeries_[i][0];
        }
        return true;
    }

    label i1 = 0;
    label i2 = n - 1;
    if (timeValue <= inputTimes_[0])
    {
        i1 = i2 = 0;
    }
    else if (timeValue >= inputTimes_[n - 1])
    {
        i1 = i2 = n - 1;
    }
    else
    {
        for (label i = 1; i < n; ++i)
        {
            if (timeValue < inputTimes_[i])
            {
                i1 = i - 1;
                i2 = i;
                break;
            }
        }
    }

    const scalar t1 = inputTimes_[i1];
    const scalar t2 = inputTimes_[i2];
    scalar w = 0.0;
    if (i1 != i2 && mag(t2 - t1) > SMALL)
    {
        w = (timeValue - t1) / (t2 - t1);
    }

    forAll(inputNames_, i)
    {
        const scalar v1 = inputSeries_[i][i1];
        const scalar v2 = inputSeries_[i][i2];
        inputValues_[i] = (1.0 - w) * v1 + w * v2;
    }

    return true;
}


labelList ecmCoupler::zoneCells() const
{
    const fvMesh& mesh = mesh_;

    const label zoneId = mesh.cellZones().findZoneID(zoneName_);
    if (zoneId < 0)
    {
        FatalErrorInFunction
            << "Cannot find cellZone '" << zoneName_ << "' in region "
            << mesh.name() << nl
            << "Available cellZones: " << mesh.cellZones().names() << nl
            << exit(FatalError);
    }

    return mesh.cellZones()[zoneId];
}


labelList ecmCoupler::cellKeys(const labelList& cells) const
{
    const fvMesh& mesh = mesh_;

    labelList keys(cells.size(), -1);

    const bool useGlobal = (keyMode_ == "globalCellId");

    if (Pstream::parRun() && useGlobal)
    {
        globalIndex gi(mesh.nCells());
        forAll(cells, i)
        {
            keys[i] = gi.toGlobal(cells[i]);
        }
    }
    else
    {
        // local cell label keys
        forAll(cells, i)
        {
            keys[i] = cells[i];
        }
    }

    return keys;
}


bool ecmCoupler::writeInput(const labelList& keys, const scalarField& Tvals, const uint64_t stepId) const
{
    return writeInputWithTime(keys, Tvals, stepId, mesh_.time().value(), mesh_.time().deltaTValue());
}


bool ecmCoupler::writeInputWithTime
(
    const labelList& keys,
    const scalarField& Tvals,
    const uint64_t stepId,
    const scalar timeValue,
    const scalar deltaT
) const
{
    if (keys.size() != Tvals.size())
    {
        FatalErrorInFunction
            << "keys.size() != Tvals.size()" << exit(FatalError);
    }

    // Only master writes in parallel masterGather mode
    const bool masterOnly = Pstream::parRun() && parallelMode_ == "masterGather";
    if (masterOnly && !Pstream::master())
    {
        return true;
    }

    const fileName inTmp = tmpName(inFile_);
    mkDir(inFile_.path());

    std::ofstream os(inTmp.c_str(), std::ios::binary | std::ios::trunc);
    if (!os.good())
    {
        WarningInFunction << "Failed to open " << inTmp << " for writing" << nl;
        return false;
    }

    HeaderInfo h{};
    h.fileType = 1u;
    h.version = 2u;
    h.N = static_cast<uint32_t>(keys.size());
    h.time = timeValue;
    h.deltaT = deltaT;
    h.keyMode = (keyMode_ == "globalCellId") ? 0u : 1u;
    h.nInputs = static_cast<uint32_t>(inputNames_.size());
    h.stepId = stepId;

    if (!writeHeaderV2(os, h))
    {
        WarningInFunction << "Failed to write header to " << inTmp << nl;
        return false;
    }

    // electricalInputs section
    forAll(inputNames_, i)
    {
        const std::string name = inputNames_[i];
        const uint32_t len = static_cast<uint32_t>(name.size());
        os.write(reinterpret_cast<const char*>(&len), sizeof(len));
        os.write(name.data(), len);
        const double val = inputValues_[i];
        os.write(reinterpret_cast<const char*>(&val), sizeof(val));
    }

    // records
    forAll(keys, i)
    {
        const int32_t k = static_cast<int32_t>(keys[i]);
        const double T = static_cast<double>(Tvals[i]);
        os.write(reinterpret_cast<const char*>(&k), sizeof(k));
        os.write(reinterpret_cast<const char*>(&T), sizeof(T));
    }

    os.close();
    if (!os)
    {
        WarningInFunction << "Write failed for " << inTmp << nl;
        return false;
    }

    // Atomic rename
    rm(inFile_);
    mv(inTmp, inFile_);

    return true;
}


bool ecmCoupler::runExternal()
{
    const bool masterOnly = Pstream::parRun() && parallelMode_ == "masterGather";
    if (masterOnly && !Pstream::master())
    {
        lastReturnCode_ = 0;
        return true;
    }

    const int ret = Foam::system(command_.c_str());
    lastReturnCode_ = ret;
    if (ret != 0)
    {
        WarningInFunction
            << "External ECM command failed (return code " << ret << "): "
            << command_ << nl;
        return false;
    }

    return true;
}


bool ecmCoupler::startPersistentWrapper()
{
    if (persistentPid_ > 0) return true;

    int pipeIn[2], pipeOut[2];
    if (::pipe(pipeIn) != 0 || ::pipe(pipeOut) != 0)
    {
        WarningInFunction << "Failed to create pipes for persistent ECM wrapper" << nl;
        return false;
    }

    pid_t pid = ::fork();
    if (pid < 0)
    {
        WarningInFunction << "fork() failed for persistent ECM wrapper" << nl;
        close(pipeIn[0]); close(pipeIn[1]);
        close(pipeOut[0]); close(pipeOut[1]);
        return false;
    }

    if (pid == 0)
    {
        dup2(pipeIn[0],  STDIN_FILENO);
        dup2(pipeOut[1], STDOUT_FILENO);
        close(pipeIn[0]); close(pipeIn[1]);
        close(pipeOut[0]); close(pipeOut[1]);
        execl("/bin/sh", "sh", "-c", command_.c_str(), nullptr);
        _exit(127);
    }

    close(pipeIn[0]);
    close(pipeOut[1]);
    persistentPid_      = pid;
    persistentStdinFd_  = pipeIn[1];
    persistentStdoutFd_ = pipeOut[0];

    Info << "ecmCoupler: persistent wrapper started (pid=" << pid << ")" << nl;
    return true;
}


bool ecmCoupler::callPersistentWrapper
(
    const std::string& request,
    std::string& response
)
{
    if (!startPersistentWrapper()) return false;

    std::string msg = request + "\n";
    const char* ptr = msg.c_str();
    ssize_t rem = static_cast<ssize_t>(msg.size());
    while (rem > 0)
    {
        ssize_t n = ::write(persistentStdinFd_, ptr, static_cast<size_t>(rem));
        if (n <= 0)
        {
            WarningInFunction << "Write to persistent wrapper stdin failed" << nl;
            stopPersistentWrapper();
            return false;
        }
        ptr += n;
        rem -= n;
    }

    response.clear();
    char ch;
    while (true)
    {
        ssize_t r = ::read(persistentStdoutFd_, &ch, 1);
        if (r <= 0)
        {
            WarningInFunction << "Persistent wrapper stdout closed unexpectedly" << nl;
            stopPersistentWrapper();
            return false;
        }
        if (ch == '\n') break;
        response += ch;
    }

    return !response.empty();
}


bool ecmCoupler::callPersistentWrapperBinary
(
    const std::string& request,
    std::string& response
)
{
    if (!startPersistentWrapper()) return false;

    const uint64_t reqSize = static_cast<uint64_t>(request.size());
    const char* sizePtr = reinterpret_cast<const char*>(&reqSize);
    ssize_t rem = static_cast<ssize_t>(sizeof(reqSize));
    while (rem > 0)
    {
        ssize_t n = ::write(persistentStdinFd_, sizePtr, static_cast<size_t>(rem));
        if (n <= 0)
        {
            WarningInFunction << "Write of binary request size to persistent wrapper failed" << nl;
            stopPersistentWrapper();
            return false;
        }
        sizePtr += n;
        rem -= n;
    }

    const char* ptr = request.data();
    rem = static_cast<ssize_t>(request.size());
    while (rem > 0)
    {
        ssize_t n = ::write(persistentStdinFd_, ptr, static_cast<size_t>(rem));
        if (n <= 0)
        {
            WarningInFunction << "Write of binary request payload to persistent wrapper failed" << nl;
            stopPersistentWrapper();
            return false;
        }
        ptr += n;
        rem -= n;
    }

    uint64_t respSize = 0;
    char* respSizePtr = reinterpret_cast<char*>(&respSize);
    rem = static_cast<ssize_t>(sizeof(respSize));
    while (rem > 0)
    {
        ssize_t n = ::read(persistentStdoutFd_, respSizePtr, static_cast<size_t>(rem));
        if (n <= 0)
        {
            WarningInFunction << "Read of binary response size from persistent wrapper failed" << nl;
            stopPersistentWrapper();
            return false;
        }
        respSizePtr += n;
        rem -= n;
    }

    response.resize(static_cast<size_t>(respSize));
    char* outPtr = response.data();
    rem = static_cast<ssize_t>(respSize);
    while (rem > 0)
    {
        ssize_t n = ::read(persistentStdoutFd_, outPtr, static_cast<size_t>(rem));
        if (n <= 0)
        {
            WarningInFunction << "Read of binary response payload from persistent wrapper failed" << nl;
            stopPersistentWrapper();
            return false;
        }
        outPtr += n;
        rem -= n;
    }

    return true;
}


void ecmCoupler::stopPersistentWrapper()
{
    if (persistentStdinFd_ >= 0)  { close(persistentStdinFd_);  persistentStdinFd_  = -1; }
    if (persistentStdoutFd_ >= 0) { close(persistentStdoutFd_); persistentStdoutFd_ = -1; }
    if (persistentPid_ > 0)
    {
        ::kill(persistentPid_, SIGTERM);
        int status = 0;
        ::waitpid(persistentPid_, &status, 0);
        persistentPid_ = -1;
    }
}


std::string ecmCoupler::buildWrapperRequestJson
(
    const scalar TcellC,
    const scalar dt,
    const scalar timeValue,
    const scalar currentA,
    const uint64_t stepId
) const
{
    std::ostringstream os;
    os.setf(std::ios::scientific);
    os << std::setprecision(16);

    const bool resetState =
        wrapperStateReset_ ||
        (
            !restartCheckpointRestored_
         && ((stepId <= 1u) || (lastGoodStepId_ > 0 && stepId <= lastGoodStepId_))
        );

    os << "{\"magic\":\"ECM_COUPLING_INPUT\",\"version\":1,";
    os << "\"step_id\":" << static_cast<unsigned long long>(stepId) << ",";
    os << "\"time_s\":" << timeValue << ",";
    os << "\"dt_s\":" << dt << ",";
    os << "\"electrical_mode\":\"current\",";
    os << "\"current_a\":" << currentA << ",";
    os << "\"T_jellyroll_degC\":" << TcellC << ",";
    os << "\"reset_state\":" << (resetState ? "true" : "false") << ",";
    os << "\"init_state\":{\"q_ah\":" << qAh_ << ",";
    os << "\"v_rc\":[" << vRc1_ << "," << vRc2_ << "],";
    os << "\"hysteresis\":" << hysteresis_ << "}}";

    std::string result = os.str();
    // DEBUG: Log first 500 chars of generated JSON
    if (stepId <= 16010u)  // Log first few steps
    {
        std::cerr << "DEBUG buildWrapperRequestJson: " << result.substr(0, 500) << std::endl;
    }
    return result;
}


std::string ecmCoupler::buildElementWisePipeRequestJson
(
    const labelList& keys,
    const scalarField& Tvals,
    const scalar dt,
    const scalar timeValue,
    const uint64_t stepId,
    const scalar tEffK
) const
{
    std::ostringstream os;
    os.setf(std::ios::scientific);
    os << std::setprecision(16);

    const label keyModeInt = (keyMode_ == "localCellId") ? 1 : 0;

    os << "{\"magic\":\"ECM_ELEMENTWISE_PIPE\",\"version\":1,";
    os << "\"step_id\":" << static_cast<unsigned long long>(stepId) << ",";
    os << "\"time_s\":" << timeValue << ",";
    os << "\"dt_s\":" << dt << ",";
    os << "\"key_mode\":" << keyModeInt << ",";
    os << "\"electrical_inputs\":{";
    forAll(inputNames_, i)
    {
        if (i) os << ",";
        os << "\"" << inputNames_[i] << "\":" << inputValues_[i];
    }
    if (inputNames_.size()) os << ",";
    os << "\"T_eff_K\":" << tEffK;
    os << "},\"records\":[";
    forAll(keys, i)
    {
        if (i) os << ",";
        os << "[" << keys[i] << "," << Tvals[i] << "]";
    }
    os << "]}";

    return os.str();
}


std::string ecmCoupler::buildElementWisePipeRequestBinary
(
    const labelList& keys,
    const scalarField& Tvals,
    const scalar dt,
    const scalar timeValue,
    const uint64_t stepId,
    const scalar tEffK
) const
{
    if (keys.size() != Tvals.size())
    {
        FatalErrorInFunction << "keys.size() != Tvals.size()" << exit(FatalError);
    }

    HeaderInfo info;
    info.fileType = 1u;
    info.version = 2u;
    info.N = static_cast<uint32_t>(keys.size());
    info.time = timeValue;
    info.deltaT = dt;
    info.keyMode = (keyMode_ == "localCellId") ? 1u : 0u;
    info.nInputs = static_cast<uint32_t>(inputNames_.size() + 1);
    info.stepId = stepId;

    std::ostringstream os(std::ios::binary);
    if (!writeHeaderV2(os, info))
    {
        FatalErrorInFunction << "Failed to serialize binary pipe header" << exit(FatalError);
    }

    forAll(inputNames_, i)
    {
        const word& name = inputNames_[i];
        const uint32_t len = static_cast<uint32_t>(name.size());
        const double val = static_cast<double>(inputValues_[i]);
        os.write(reinterpret_cast<const char*>(&len), sizeof(len));
        os.write(name.c_str(), len);
        os.write(reinterpret_cast<const char*>(&val), sizeof(val));
    }

    {
        const std::string name("T_eff_K");
        const uint32_t len = static_cast<uint32_t>(name.size());
        const double val = static_cast<double>(tEffK);
        os.write(reinterpret_cast<const char*>(&len), sizeof(len));
        os.write(name.c_str(), len);
        os.write(reinterpret_cast<const char*>(&val), sizeof(val));
    }

    forAll(keys, i)
    {
        const int32_t k = static_cast<int32_t>(keys[i]);
        const double T = static_cast<double>(Tvals[i]);
        os.write(reinterpret_cast<const char*>(&k), sizeof(k));
        os.write(reinterpret_cast<const char*>(&T), sizeof(T));
    }

    return os.str();
}


bool ecmCoupler::readOutput(HashTable<scalar, label>& qByKey, const uint64_t expectedStepId, uint64_t& outStepId) const
{
    qByKey.clear();
    outStepId = 0;

    const bool masterOnly = Pstream::parRun() && parallelMode_ == "masterGather";

    // In masterGather, master reads and broadcasts
    std::vector<int32_t> keys;
    std::vector<double> qvals;

    if (!masterOnly || Pstream::master())
    {
        std::ifstream is(outFile_.c_str(), std::ios::binary);
        if (!is.good())
        {
            WarningInFunction << "Missing ECM output file: " << outFile_ << nl;
            return false;
        }

        HeaderInfo h{};
        if (!readHeader(is, h) || h.fileType != 2u)
        {
            WarningInFunction << "Invalid ECM output header in " << outFile_ << nl;
            return false;
        }

        if (h.version < 1u || h.version > 2u)
        {
            WarningInFunction
                << "Unsupported ECM output header version " << h.version
                << " in " << outFile_ << nl;
            return false;
        }

        if (h.version >= 2u)
        {
            outStepId = h.stepId;
            if (outStepId != expectedStepId)
            {
                WarningInFunction
                    << "ECM output stepId mismatch. Expected " << expectedStepId
                    << ", got " << outStepId << ". Keeping previous values." << nl;
                return false;
            }
        }
        else
        {
            WarningInFunction
                << "ECM output is version 1 (no stepId). "
                << "Proceeding without transactional check." << nl;
        }

        // Skip any inputs section (should be 0, but tolerate >0)
        for (uint32_t i = 0; i < h.nInputs; ++i)
        {
            uint32_t len = 0;
            is.read(reinterpret_cast<char*>(&len), sizeof(len));
            if (!is.good()) return false;
            is.seekg(len, std::ios::cur);
            double val = 0.0;
            is.read(reinterpret_cast<char*>(&val), sizeof(val));
            if (!is.good()) return false;
        }

        keys.resize(h.N);
        qvals.resize(h.N);

        for (uint32_t i = 0; i < h.N; ++i)
        {
            int32_t k = 0;
            double q = 0.0;
            is.read(reinterpret_cast<char*>(&k), sizeof(k));
            is.read(reinterpret_cast<char*>(&q), sizeof(q));
            if (!is.good())
            {
                WarningInFunction << "Truncated ECM output records" << nl;
                return false;
            }
            keys[i] = k;
            qvals[i] = q;
        }
    }

    if (masterOnly)
    {
        // Broadcast sizes then data
        label n = static_cast<label>(keys.size());
        Pstream::broadcast(n);

        if (!Pstream::master())
        {
            keys.resize(n);
            qvals.resize(n);
        }

        label stepIdLabel = static_cast<label>(outStepId);
        Pstream::broadcast(stepIdLabel);
        outStepId = static_cast<uint64_t>(stepIdLabel);

        // Broadcast as FOAM Lists
        List<label> kL(n);
        List<scalar> qL(n);

        if (Pstream::master())
        {
            for (label i = 0; i < n; ++i)
            {
                kL[i] = static_cast<label>(keys[i]);
                qL[i] = static_cast<scalar>(qvals[i]);
            }
        }

        Pstream::broadcast(kL);
        Pstream::broadcast(qL);

        // Fill qByKey from broadcast
        forAll(kL, i)
        {
            qByKey.insert(kL[i], qL[i]);
        }
    }
    else
    {
        // Serial (or parRun but serialOnly): fill directly
        for (size_t i = 0; i < keys.size(); ++i)
        {
            qByKey.insert(static_cast<label>(keys[i]), static_cast<scalar>(qvals[i]));
        }
    }

    return true;
}


bool ecmCoupler::parseOutputBuffer
(
    const std::string& buffer,
    HashTable<scalar, label>& qByKey,
    const uint64_t expectedStepId,
    uint64_t& outStepId
) const
{
    qByKey.clear();
    outStepId = 0;

    std::istringstream is(buffer, std::ios::binary);

    HeaderInfo h{};
    if (!readHeader(is, h) || h.fileType != 2u)
    {
        WarningInFunction << "Invalid ECM output header in binary pipe response" << nl;
        return false;
    }

    if (h.version < 1u || h.version > 2u)
    {
        WarningInFunction
            << "Unsupported ECM output header version " << h.version
            << " in binary pipe response" << nl;
        return false;
    }

    if (h.version >= 2u)
    {
        outStepId = h.stepId;
        if (outStepId != expectedStepId)
        {
            WarningInFunction
                << "ECM output stepId mismatch. Expected " << expectedStepId
                << ", got " << outStepId << ". Keeping previous values." << nl;
            return false;
        }
    }

    for (uint32_t i = 0; i < h.nInputs; ++i)
    {
        uint32_t len = 0;
        is.read(reinterpret_cast<char*>(&len), sizeof(len));
        if (!is.good()) return false;
        is.seekg(len, std::ios::cur);
        double val = 0.0;
        is.read(reinterpret_cast<char*>(&val), sizeof(val));
        if (!is.good()) return false;
    }

    for (uint32_t i = 0; i < h.N; ++i)
    {
        int32_t k = 0;
        double q = 0.0;
        is.read(reinterpret_cast<char*>(&k), sizeof(k));
        is.read(reinterpret_cast<char*>(&q), sizeof(q));
        if (!is.good())
        {
            WarningInFunction << "Truncated ECM output records in binary pipe response" << nl;
            return false;
        }
        qByKey.insert(static_cast<label>(k), static_cast<scalar>(q));
    }

    return true;
}

bool ecmCoupler::writeLastGoodSnapshot(
    const HashTable<scalar, label>& qByKey,
    const uint64_t stepId,
    const scalar timeValue,
    const scalar qSum,
    const label returnCode
) const
{
    if (lastGoodFile_.empty())
    {
        return true;
    }

    const bool masterOnly = Pstream::parRun() && parallelMode_ == "masterGather";
    if (masterOnly && !Pstream::master())
    {
        return true;
    }

    const fileName tmpFile = tmpName(lastGoodFile_);
    mkDir(lastGoodFile_.path());

    std::ofstream os(tmpFile.c_str(), std::ios::binary | std::ios::trunc);
    if (!os.good())
    {
        WarningInFunction << "Failed to open " << tmpFile << " for writing" << nl;
        return false;
    }

    LastGoodHeader h{};
    setLastGoodMagic(h.magic);
    h.version = 1u;
    h.stepId = stepId;
    h.time = timeValue;
    h.qSum = qSum;
    h.returnCode = static_cast<int32_t>(returnCode);
    h.N = static_cast<uint32_t>(qByKey.size());

    os.write(reinterpret_cast<const char*>(&h), sizeof(h));

    typedef HashTable<scalar, label> QTable;
    forAllConstIter(QTable, qByKey, iter)
    {
        const int32_t k = static_cast<int32_t>(iter.key());
        const double q = static_cast<double>(iter());
        os.write(reinterpret_cast<const char*>(&k), sizeof(k));
        os.write(reinterpret_cast<const char*>(&q), sizeof(q));
    }

    os.close();
    if (!os)
    {
        WarningInFunction << "Write failed for " << tmpFile << nl;
        return false;
    }

    rm(lastGoodFile_);
    mv(tmpFile, lastGoodFile_);

    return true;
}

bool ecmCoupler::readLastGoodSnapshot()
{
    if (lastGoodFile_.empty())
    {
        return false;
    }

    std::ifstream is(lastGoodFile_.c_str(), std::ios::binary);
    if (!is.good())
    {
        return false;
    }

    LastGoodHeader h{};
    is.read(reinterpret_cast<char*>(&h), sizeof(h));
    if (!is.good() || !checkLastGoodMagic(h.magic))
    {
        WarningInFunction << "Invalid last-good snapshot header in " << lastGoodFile_ << nl;
        return false;
    }

    if (h.version != 1u)
    {
        WarningInFunction
            << "Unsupported last-good snapshot version " << h.version
            << " in " << lastGoodFile_ << nl;
        return false;
    }

    const scalar currentTime = mesh_.time().value();
    if (h.time > currentTime + SMALL)
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "Ignoring last-good snapshot at time " << h.time
                << " because current restart time is " << currentTime << nl;
        }
        return false;
    }

    HashTable<scalar, label> qByKey;
    for (uint32_t i = 0; i < h.N; ++i)
    {
        int32_t k = 0;
        double q = 0.0;
        is.read(reinterpret_cast<char*>(&k), sizeof(k));
        is.read(reinterpret_cast<char*>(&q), sizeof(q));
        if (!is.good())
        {
            WarningInFunction << "Truncated last-good snapshot records in " << lastGoodFile_ << nl;
            return false;
        }
        qByKey.insert(static_cast<label>(k), static_cast<scalar>(q));
    }

    lastGoodStepId_ = h.stepId;
    lastGoodTime_ = h.time;
    lastGoodQSum_ = h.qSum;
    lastReturnCode_ = static_cast<label>(h.returnCode);
    lastGoodQByKey_ = qByKey;

    return true;
}

void ecmCoupler::initializeStartupFields()
{
    fvMesh& mesh = const_cast<fvMesh&>(mesh_);
    volScalarField& qField = mesh.lookupObjectRef<volScalarField>(qFieldName_);
    volScalarField* stFieldPtr = nullptr;

    if (outputMode_ == "temperatureSource" && mesh.foundObject<volScalarField>(stFieldName_))
    {
        stFieldPtr = &mesh.lookupObjectRef<volScalarField>(stFieldName_);
    }

    // Exact restart checkpoint means the OpenFOAM time directory and coupler state
    // are expected to be consistent. Preserve the field loaded from that time directory.
    if (restartCheckpointRestored_)
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            Info<< "Keeping " << qFieldName_
                << " from restart time directory (exact checkpoint restored)." << nl;
        }
        return;
    }

    auto clearStartupFields = [&]()
    {
        const label nCells = mesh.nCells();
        for (label cellI = 0; cellI < nCells; ++cellI)
        {
            qField[cellI] = 0.0;
            if (stFieldPtr)
            {
                (*stFieldPtr)[cellI] = 0.0;
            }
        }
        qField.correctBoundaryConditions();
        if (stFieldPtr)
        {
            stFieldPtr->correctBoundaryConditions();
        }
    };

    if (restartCheckpointReconstructed_ && !lastGoodQByKey_.empty())
    {
        clearStartupFields();

        const labelList cells = zoneCells();
        const scalar alphaSaved = alpha_;
        alpha_ = 1.0;

        scalar qSum = 0.0;
        if (couplingMode_ == "lumped")
        {
            label lumpedKey = 0;
            if (!lastGoodQByKey_.empty())
            {
                lumpedKey = lastGoodQByKey_.begin().key();
            }
            qSum = updateFieldsLumped(cells, lumpedKey, lastGoodQByKey_);
        }
        else
        {
            qSum = updateFieldsElementWise(labelList(), lastGoodQByKey_);
        }

        alpha_ = alphaSaved;
        lastGoodQSum_ = qSum;

        if (Pstream::master() || !Pstream::parRun())
        {
            Info<< "Initialized " << qFieldName_
                << " from reconstructed checkpoint source." << nl;
        }
        return;
    }

    clearStartupFields();

    if (Pstream::master() || !Pstream::parRun())
    {
        Info<< "Reset " << qFieldName_
            << " across the region to zero (no exact restart checkpoint)." << nl;
    }
}


void ecmCoupler::ensureFields()
{
    fvMesh& mesh = const_cast<fvMesh&>(mesh_);
    const IOobject::writeOption writeOpt = writeFields_ ? IOobject::AUTO_WRITE : IOobject::NO_WRITE;
    const IOobject::readOption readOpt = IOobject::READ_IF_PRESENT;

    // ecmQdot [W/m^3]
    if (!mesh.foundObject<volScalarField>(qFieldName_))
    {
        dimensionSet dimsQ(1, -1, -3, 0, 0, 0, 0); // [kg m^-1 s^-3] = W/m^3
        volScalarField* qPtr = new volScalarField
        (
            IOobject
            (
                qFieldName_,
                mesh.time().timeName(),
                mesh,
                readOpt,
                writeOpt
            ),
            mesh,
            dimensionedScalar(qFieldName_, dimsQ, 0.0)
        );
        mesh.objectRegistry::store(qPtr);
    }
    else
    {
        mesh.lookupObjectRef<volScalarField>(qFieldName_).writeOpt(writeOpt);
    }

    // ecmST [K/s]
    if (outputMode_ == "temperatureSource" && !mesh.foundObject<volScalarField>(stFieldName_))
    {
        dimensionSet dimsST(0, 0, -1, 1, 0, 0, 0); // Theta / time
        volScalarField* stPtr = new volScalarField
        (
            IOobject
            (
                stFieldName_,
                mesh.time().timeName(),
                mesh,
                readOpt,
                writeOpt
            ),
            mesh,
            dimensionedScalar(stFieldName_, dimsST, 0.0)
        );
        mesh.objectRegistry::store(stPtr);
    }
    else if (outputMode_ == "temperatureSource" && mesh.foundObject<volScalarField>(stFieldName_))
    {
        mesh.lookupObjectRef<volScalarField>(stFieldName_).writeOpt(writeOpt);
    }
}


scalar ecmCoupler::updateFieldsElementWise(const labelList& keys, const HashTable<scalar, label>& qByKey)
{
    fvMesh& mesh = const_cast<fvMesh&>(mesh_);

    volScalarField& qField = mesh.lookupObjectRef<volScalarField>(qFieldName_);
    volScalarField* stFieldPtr = nullptr;

    if (outputMode_ == "temperatureSource")
    {
        if (rhoCp_ <= SMALL)
        {
            FatalErrorInFunction
                << "outputMode=temperatureSource requires rhoCp > 0 (J/m^3/K). "
                << "Current rhoCp=" << rhoCp_ << exit(FatalError);
        }
        stFieldPtr = &mesh.lookupObjectRef<volScalarField>(stFieldName_);
    }

    const labelList cells = zoneCells();
    const labelList cellKeyList = cellKeys(cells);

    if (cells.size() != cellKeyList.size())
    {
        FatalErrorInFunction << "Internal: cells.size()!=cellKeyList.size()" << exit(FatalError);
    }

    label nMissing = 0;
    label nMatched = 0;
    scalar qSum = 0.0;
    const scalarField& V = mesh.V();

    forAll(cells, i)
    {
        const label cellI = cells[i];
        const label key = cellKeyList[i];

        // When element mapping active, translate globalCellId -> ecmElementId
        label lookupKey = key;
        if (hasElementMapping_)
        {
            auto eIt = cellToEcmElement_.find(static_cast<int>(key));
            if (eIt == cellToEcmElement_.end())
            {
                nMissing++;
                continue;
            }
            lookupKey = static_cast<label>(eIt->second);
        }

        HashTable<scalar, label>::const_iterator iter = qByKey.find(lookupKey);
        if (!iter.found())
        {
            nMissing++;
            continue; // keep old value
        }

        const scalar qNew = *iter;
        const scalar qOld = qField[cellI];
        const scalar qApplied = alpha_*qNew + (1.0 - alpha_)*qOld;

        qField[cellI] = qApplied;
        qSum += qApplied * V[cellI];
        nMatched++;

        if (stFieldPtr)
        {
            (*stFieldPtr)[cellI] = qApplied / rhoCp_;
        }
    }

    if (nMissing > 0 && (Pstream::master() || !Pstream::parRun()))
    {
        WarningInFunction
            << "ECM output missing " << nMissing << " keys for zone '" << zoneName_
            << "'. Keeping previous values for those cells." << nl;
    }

    label nExtra = 0;
    if (qByKey.size() > static_cast<label>(nMatched))
    {
        nExtra = static_cast<label>(qByKey.size()) - nMatched;
    }

    if ((nMissing > 0 || nExtra > 0) && (Pstream::master() || !Pstream::parRun()))
    {
        WarningInFunction
            << "ECM mapping summary: expected=" << cells.size()
            << " received=" << qByKey.size()
            << " matched=" << nMatched
            << " missing=" << nMissing
            << " extra=" << nExtra << nl;
    }

    reduce(qSum, sumOp<scalar>());

    qField.correctBoundaryConditions();
    if (stFieldPtr) stFieldPtr->correctBoundaryConditions();

    return qSum;
}

scalar ecmCoupler::updateFieldsLumped(const labelList& cells, const label lumpedKey, const HashTable<scalar, label>& qByKey)
{
    fvMesh& mesh = const_cast<fvMesh&>(mesh_);

    volScalarField& qField = mesh.lookupObjectRef<volScalarField>(qFieldName_);
    volScalarField* stFieldPtr = nullptr;

    if (outputMode_ == "temperatureSource")
    {
        if (rhoCp_ <= SMALL)
        {
            FatalErrorInFunction
                << "outputMode=temperatureSource requires rhoCp > 0 (J/m^3/K). "
                << "Current rhoCp=" << rhoCp_ << exit(FatalError);
        }
        stFieldPtr = &mesh.lookupObjectRef<volScalarField>(stFieldName_);
    }

    if (qByKey.empty())
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction << "ECM output missing lumped record; keeping previous values." << nl;
        }
        return 0.0;
    }

    scalar qOut = 0.0;
    HashTable<scalar, label>::const_iterator iter = qByKey.find(lumpedKey);
    if (iter.found())
    {
        qOut = *iter;
    }
    else
    {
        HashTable<scalar, label>::const_iterator firstIter = qByKey.begin();
        qOut = firstIter();
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "ECM output missing lumped key " << lumpedKey
                << "; using first available record." << nl;
        }
    }

    const scalarField& V = mesh.V();
    scalar totalVol = 0.0;
    forAll(cells, i)
    {
        totalVol += V[cells[i]];
    }
    reduce(totalVol, sumOp<scalar>());

    if (totalVol <= SMALL)
    {
        WarningInFunction << "Total coupled volume is too small; keeping previous values." << nl;
        return 0.0;
    }

    scalar qVol = qOut;
    if (lumpedOutput_ == "totalPower")
    {
        qVol = qOut / (totalVol * totalVolumeScale_);
    }
    else if (lumpedOutput_ != "volumetric")
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "Unknown lumpedOutput '" << lumpedOutput_
                << "', using volumetric output." << nl;
        }
    }

    bool useAxialProfile = false;
    if (axialProfile_ == "linear")
    {
        useAxialProfile = true;
    }
    else if (axialProfile_ != "uniform" && (Pstream::master() || !Pstream::parRun()))
    {
        WarningInFunction
            << "Unknown axialProfile '" << axialProfile_
            << "', using uniform distribution." << nl;
    }

    vector axis = axialAxis_;
    scalar axisMag = mag(axis);
    if (axisMag <= SMALL)
    {
        axis = vector(0, 0, 1);
        axisMag = 1.0;
    }
    axis /= axisMag;

    scalar sMin = GREAT;
    scalar sMax = -GREAT;
    const vectorField& C = mesh.C();
    if (useAxialProfile)
    {
        forAll(cells, i)
        {
            const scalar s = (C[cells[i]] - axialOrigin_) & axis;
            sMin = min(sMin, s);
            sMax = max(sMax, s);
        }
        reduce(sMin, minOp<scalar>());
        reduce(sMax, maxOp<scalar>());
        if (mag(sMax - sMin) <= SMALL)
        {
            useAxialProfile = false;
            if (Pstream::master() || !Pstream::parRun())
            {
                WarningInFunction
                    << "axialProfile linear requires non-zero axial extent; using uniform." << nl;
            }
        }
    }

    scalar avgWeight = 1.0;
    if (useAxialProfile)
    {
        scalar sumWeightV = 0.0;
        forAll(cells, i)
        {
            const scalar s = (C[cells[i]] - axialOrigin_) & axis;
            const scalar xi = (s - sMin) / (sMax - sMin);
            const scalar bias = min(1.0, max(-1.0, axialBias_));
            const scalar w = max(SMALL, 1.0 + bias*(2.0*xi - 1.0));
            sumWeightV += w * V[cells[i]];
        }
        reduce(sumWeightV, sumOp<scalar>());
        if (sumWeightV > SMALL && totalVol > SMALL)
        {
            avgWeight = sumWeightV / totalVol;
        }
    }

    forAll(cells, i)
    {
        const label cellI = cells[i];
        scalar qVolCell = qVol;
        if (useAxialProfile && avgWeight > SMALL)
        {
            const scalar s = (C[cellI] - axialOrigin_) & axis;
            const scalar xi = (s - sMin) / (sMax - sMin);
            const scalar bias = min(1.0, max(-1.0, axialBias_));
            const scalar w = max(SMALL, 1.0 + bias*(2.0*xi - 1.0));
            qVolCell = qVol * w / avgWeight;
        }

        const scalar qOld = qField[cellI];
        const scalar qApplied = alpha_*qVolCell + (1.0 - alpha_)*qOld;

        qField[cellI] = qApplied;

        if (stFieldPtr)
        {
            (*stFieldPtr)[cellI] = qApplied / rhoCp_;
        }
    }

    qField.correctBoundaryConditions();
    if (stFieldPtr) stFieldPtr->correctBoundaryConditions();

    if (lumpedOutput_ == "totalPower" && (Pstream::master() || !Pstream::parRun()))
    {
        const scalar qSum = qVol * totalVol;
        const scalar tol = max(1e-6, 1e-3*mag(qOut));
        if (mag(qSum - qOut) > tol)
        {
            WarningInFunction
                << "Q_sum_check mismatch (expected Q_total=" << qOut
                << " W, got " << qSum << " W)." << nl;
        }
    }

    return qVol * totalVol;
}

scalar ecmCoupler::computeTEff(const labelList& cells, const volScalarField& T) const
{
    const fvMesh& mesh = mesh_;
    const scalarField& V = mesh.V();
    const vectorField& C = mesh.C();

    if (tEffMode_ == "sensorEmulation")
    {
        const label sensorZoneId = mesh.cellZones().findZoneID(sensorZoneName_);
        if (sensorZoneId >= 0)
        {
            const labelList& sensorCells = mesh.cellZones()[sensorZoneId];
            scalar sumTV = 0.0;
            scalar sumV = 0.0;
            forAll(sensorCells, i)
            {
                const label c = sensorCells[i];
                sumTV += T[c] * V[c];
                sumV += V[c];
            }
            reduce(sumTV, sumOp<scalar>());
            reduce(sumV, sumOp<scalar>());
            if (sumV > SMALL)
            {
                return sumTV / sumV;
            }
        }
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "sensorEmulation requires sensorZone; falling back to volumeAverage." << nl;
        }
    }

    if (tEffMode_ == "coreWeighted")
    {
        vector axis = coreAxis_;
        scalar axisMag = mag(axis);
        if (axisMag <= SMALL)
        {
            axis = vector(0, 0, 1);
            axisMag = 1.0;
        }
        axis /= axisMag;

        scalar sumWT = 0.0;
        scalar sumW = 0.0;
        forAll(cells, i)
        {
            const label c = cells[i];
            const vector rel = C[c] - coreOrigin_;
            const vector radial = rel - (rel & axis) * axis;
            const scalar r = mag(radial);
            const scalar w = V[c] / (r + SMALL);
            sumWT += T[c] * w;
            sumW += w;
        }
        reduce(sumWT, sumOp<scalar>());
        reduce(sumW, sumOp<scalar>());
        if (sumW > SMALL)
        {
            return sumWT / sumW;
        }
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "coreWeighted failed (zero weight); falling back to volumeAverage." << nl;
        }
    }

    // Default volumeAverage
    scalar sumTV = 0.0;
    scalar sumV = 0.0;
    forAll(cells, i)
    {
        const label c = cells[i];
        sumTV += T[c] * V[c];
        sumV += V[c];
    }
    reduce(sumTV, sumOp<scalar>());
    reduce(sumV, sumOp<scalar>());
    if (sumV <= SMALL)
    {
        return 0.0;
    }
    return sumTV / sumV;
}

scalar ecmCoupler::lookupInputOrDefault(const word& name, const scalar fallback) const
{
    forAll(inputNames_, i)
    {
        if (inputNames_[i] == name)
        {
            return inputValues_[i];
        }
    }
    return fallback;
}

string ecmCoupler::buildWrapperCommand(const scalar TcellC, const scalar dt) const
{
    std::ostringstream cmd;

    cmd << wrapperCommand_;
    cmd << " --mode " << wrapperMode_;
    cmd << " --dt " << dt;
    cmd << " --steps " << wrapperSteps_;
    cmd << " --temperature-mode " << wrapperTempMode_;
    cmd << " --temp-profile " << wrapperTempProfile_;
    cmd << " --temp-init " << TcellC;
    cmd << " --current-profile " << wrapperCurrentProfile_;
    cmd << " --current " << currentA_;
    cmd << " --q-ah-init " << qAh_;
    cmd << " --hysteresis-init " << hysteresis_;
    cmd << " --v-rc-init " << vRc1_ << " " << vRc2_;

    if (wrapperWriteCsv_)
    {
        cmd << " --write-csv";
        if (!wrapperCsvPrefix_.empty())
        {
            cmd << " --csv-prefix " << wrapperCsvPrefix_;
        }
    }

    if (wrapperStateReset_)
    {
        cmd << " --state-reset";
    }

    if (!wrapperExtraArgs_.empty())
    {
        cmd << " " << wrapperExtraArgs_;
    }

    return cmd.str();
}

bool ecmCoupler::readWrapperCsv(scalar& qOut, scalar& vT)
{
    qOut = 0.0;
    vT = 0.0;

    fileName csvFile = wrapperCsvFile_;
    if (csvFile.empty())
    {
        csvFile = wrapperCsvPrefix_ + "_single.csv";
    }

    std::ifstream is(csvFile.c_str());
    if (!is.good())
    {
        WarningInFunction << "Missing wrapper CSV output: " << csvFile << nl;
        return false;
    }

    std::string headerLine;
    if (!std::getline(is, headerLine))
    {
        WarningInFunction << "Wrapper CSV missing header: " << csvFile << nl;
        return false;
    }

    const std::vector<std::string> headers = splitCsvLine(headerLine);
    int heatIdx = -1;
    int qAhIdx = -1;
    int vrc1Idx = -1;
    int vrc2Idx = -1;
    int hystIdx = -1;
    int vtIdx = -1;

    for (size_t i = 0; i < headers.size(); ++i)
    {
        const std::string& h = headers[i];
        if (h == wrapperHeatColumn_) heatIdx = static_cast<int>(i);
        if (h == wrapperQAhColumn_) qAhIdx = static_cast<int>(i);
        if (h == wrapperVrc1Column_) vrc1Idx = static_cast<int>(i);
        if (h == wrapperVrc2Column_) vrc2Idx = static_cast<int>(i);
        if (h == wrapperHysteresisColumn_) hystIdx = static_cast<int>(i);
        if (h == wrapperVoltageColumn_) vtIdx = static_cast<int>(i);
    }

    if (heatIdx < 0)
    {
        WarningInFunction
            << "Wrapper CSV missing heat column '" << wrapperHeatColumn_
            << "' in " << csvFile << nl;
        return false;
    }

    std::string line;
    std::string lastLine;
    while (std::getline(is, line))
    {
        if (!trimCopy(line).empty())
        {
            lastLine = line;
        }
    }

    if (lastLine.empty())
    {
        WarningInFunction << "Wrapper CSV missing data rows: " << csvFile << nl;
        return false;
    }

    const std::vector<std::string> cols = splitCsvLine(lastLine);
    if (static_cast<int>(cols.size()) <= heatIdx)
    {
        WarningInFunction << "Wrapper CSV data row too short: " << csvFile << nl;
        return false;
    }

    try
    {
        qOut = std::stod(cols[heatIdx]);

        if (qAhIdx >= 0 && qAhIdx < static_cast<int>(cols.size()))
        {
            qAh_ = std::stod(cols[qAhIdx]);
        }
        if (vrc1Idx >= 0 && vrc1Idx < static_cast<int>(cols.size()))
        {
            vRc1_ = std::stod(cols[vrc1Idx]);
        }
        if (vrc2Idx >= 0 && vrc2Idx < static_cast<int>(cols.size()))
        {
            vRc2_ = std::stod(cols[vrc2Idx]);
        }
        if (hystIdx >= 0 && hystIdx < static_cast<int>(cols.size()))
        {
            hysteresis_ = std::stod(cols[hystIdx]);
        }
        if (vtIdx >= 0 && vtIdx < static_cast<int>(cols.size()))
        {
            vT = std::stod(cols[vtIdx]);
        }
    }
    catch (const std::exception&)
    {
        WarningInFunction << "Failed to parse wrapper CSV data row: " << csvFile << nl;
        return false;
    }

    return true;
}

bool ecmCoupler::writeWrapperJsonInput(
    const scalar TcellC,
    const scalar dt,
    const scalar timeValue,
    const scalar currentA,
    const uint64_t stepId
) const
{
    const fileName inTmp = tmpName(inFile_);
    mkDir(inFile_.path());

    std::ofstream os(inTmp.c_str(), std::ios::out | std::ios::trunc);
    if (!os.good())
    {
        WarningInFunction << "Failed to open " << inTmp << " for writing" << nl;
        return false;
    }

    os.setf(std::ios::scientific);
    os << std::setprecision(16);

    os << "{\n";
    os << "  \"magic\": \"ECM_COUPLING_INPUT\",\n";
    os << "  \"version\": 1,\n";
    os << "  \"step_id\": " << static_cast<unsigned long long>(stepId) << ",\n";
    os << "  \"time_s\": " << timeValue << ",\n";
    os << "  \"dt_s\": " << dt << ",\n";
    os << "  \"electrical_mode\": \"current\",\n";
    os << "  \"current_a\": " << currentA << ",\n";
    os << "  \"T_jellyroll_degC\": " << TcellC << ",\n";
    const bool resetState =
        wrapperStateReset_
     || (
            !restartCheckpointRestored_
         && ((stepId <= 1) || (lastGoodStepId_ > 0 && stepId <= lastGoodStepId_))
        );
    os << "  \"reset_state\": " << (resetState ? "true" : "false") << ",\n";
    os << "  \"init_state\": {\n";
    os << "    \"q_ah\": " << qAh_ << ",\n";
    os << "    \"v_rc\": [" << vRc1_ << ", " << vRc2_ << "],\n";
    os << "    \"hysteresis\": " << hysteresis_ << "\n";
    os << "  }\n";
    os << "}\n";

    os.close();
    if (!os)
    {
        WarningInFunction << "Write failed for " << inTmp << nl;
        return false;
    }

    rm(inFile_);
    mv(inTmp, inFile_);

    return true;
}

bool ecmCoupler::readWrapperJsonOutput(scalar& qOut, scalar& vT) const
{
    qOut = 0.0;
    vT = 0.0;

    std::ifstream is(outFile_.c_str());
    if (!is.good())
    {
        WarningInFunction << "Missing wrapper JSON output: " << outFile_ << nl;
        return false;
    }

    std::ostringstream buf;
    buf << is.rdbuf();
    const std::string text = buf.str();

    std::string status;
    if (!extractJsonString(text, "status", status))
    {
        WarningInFunction << "Wrapper JSON missing status field: " << outFile_ << nl;
        return false;
    }
    if (status != "ok")
    {
        std::string message;
        if (!extractJsonString(text, "message", message))
        {
            message = "unknown";
        }
        WarningInFunction
            << "Wrapper JSON status=" << status << " message=" << message
            << " in " << outFile_ << nl;
        return false;
    }

    double qVal = 0.0;
    if (!extractJsonNumber(text, "Q_GEN_W", qVal))
    {
        WarningInFunction << "Wrapper JSON missing Q_GEN_W: " << outFile_ << nl;
        return false;
    }
    qOut = static_cast<scalar>(qVal);

    double vVal = 0.0;
    if (extractJsonNumber(text, "V_T_V", vVal))
    {
        vT = static_cast<scalar>(vVal);
    }

    return true;
}

bool ecmCoupler::execute()
{
    ensureFields();

    auto persistIfWriteTime = [&]()
    {
        if (!mesh_.time().writeTime())
        {
            return;
        }

        if (!writeRestartCheckpoint() && (Pstream::master() || !Pstream::parRun()))
        {
            WarningInFunction << "Failed to persist ECM restart checkpoint." << nl;
        }

        if (!writeWriteTimeHistory() && (Pstream::master() || !Pstream::parRun()))
        {
            WarningInFunction << "Failed to persist ECM writeTime history." << nl;
        }
    };

    // Accumulate deltaT on every step regardless of whether we call ECM.
    accumulatedDt_ += mesh_.time().deltaTValue();

    // C++ step counter: skip pipe call entirely on non-real-ECM steps.
    // ecmQdot persists between steps so no re-apply is needed.
    if (callEveryNSteps_ > 1)
    {
        callStepCounter_++;
        if (callStepCounter_ < callEveryNSteps_)
        {
            if (Pstream::master() || !Pstream::parRun())
            {
                Info<< "ECM step skip (" << callStepCounter_
                    << "/" << callEveryNSteps_ << ")" << nl;
            }
            persistIfWriteTime();
            return true;
        }
        callStepCounter_ = 0;
    }

    // Consumed accumulated dt for this real ECM call; reset for next interval.
    const scalar dtForEcm = accumulatedDt_;
    accumulatedDt_ = 0.0;

    const labelList cells = zoneCells();

    if (inputMode_ == "csv")
    {
        updateElectricalInputsFromCsv(mesh_.time().value());
    }

    // Extract temperatures
    const volScalarField& T = mesh_.lookupObject<volScalarField>(TName_);

    scalarField Tvals(cells.size());
    forAll(cells, i)
    {
        Tvals[i] = T[cells[i]];
    }

    // Determine keys, possibly global and/or gathered
    labelList keysLocal = cellKeys(cells);

    // In masterGather mode, gather keys and values to master
    labelList keys;
    scalarField Tsend;

    const bool masterGather = Pstream::parRun() && parallelMode_ == "masterGather";
    const bool lumpedMode = (couplingMode_ == "lumped");

    label lumpedKey = -1;
    scalar totalVol = 0.0;

    if (lumpedMode)
    {
        const scalarField& V = mesh_.V();
        forAll(cells, i)
        {
            totalVol += V[cells[i]];
        }
        reduce(totalVol, sumOp<scalar>());

        if (totalVol <= SMALL)
        {
            WarningInFunction << "Total coupled volume is too small; skipping ECM call." << nl;
            persistIfWriteTime();
            return true;
        }

        const scalar Tavg = computeTEff(cells, T);

        if (cells.size() > 0)
        {
            lumpedKey = keysLocal[0];
        }
        else
        {
            lumpedKey = 0;
        }

        if (Pstream::parRun())
        {
            Pstream::broadcast(lumpedKey);
        }

        keys.setSize(1);
        Tsend.setSize(1);
        keys[0] = lumpedKey;
        Tsend[0] = Tavg;
    }
    else if (masterGather)
    {
        // Gather lists to master
        List<labelList> allKeys;
        List<scalarField> allT;

        allKeys = Pstream::listGatherValues(keysLocal);
        allT = Pstream::listGatherValues(Tvals);

        if (Pstream::master())
        {
            // Concatenate
            label total = 0;
            forAll(allKeys, pi) total += allKeys[pi].size();

            keys.setSize(total);
            Tsend.setSize(total);

            label idx = 0;
            forAll(allKeys, pi)
            {
                const labelList& kL = allKeys[pi];
                const scalarField& tL = allT[pi];
                forAll(kL, j)
                {
                    keys[idx] = kL[j];
                    Tsend[idx] = tL[j];
                    idx++;
                }
            }
        }
    }
    else
    {
        keys = keysLocal;
        Tsend = Tvals;
    }

    // Element mapping: aggregate all cell temps to ECM element averages on master
    if (hasElementMapping_ && !lumpedMode && (Pstream::master() || !Pstream::parRun()))
    {
        scalarField elemTsum(nEcmElements_, scalar(0));
        labelField elemCount(nEcmElements_, label(0));

        forAll(keys, i)
        {
            auto eIt = cellToEcmElement_.find(static_cast<int>(keys[i]));
            if (eIt != cellToEcmElement_.end())
            {
                const label eId = static_cast<label>(eIt->second);
                if (eId >= 0 && eId < nEcmElements_)
                {
                    elemTsum[eId] += Tsend[i];
                    elemCount[eId]++;
                }
            }
        }

        keys.setSize(nEcmElements_);
        Tsend.setSize(nEcmElements_);
        for (label e = 0; e < nEcmElements_; e++)
        {
            keys[e] = e;
            Tsend[e] = (elemCount[e] > 0) ? elemTsum[e] / elemCount[e] : scalar(300.0);
        }

        Info<< "ECM element aggregation: " << nEcmElements_
            << " elements; T range [" << min(Tsend) << ", " << max(Tsend) << "] K" << nl;
    }

    stepId_ = static_cast<uint64_t>(mesh_.time().timeIndex());

    bool outputOk = true;
    HashTable<scalar, label> qByKey;
    uint64_t outStepId = 0;

    label nSubIter = subIterations_;
    if (nSubIter < 1)
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "subIterations must be >= 1; using 1." << nl;
        }
        nSubIter = 1;
    }

    const scalar dtFull = dtForEcm;   // accumulated since last real ECM call
    const scalar timeFull = mesh_.time().value();
    const scalar dtSub = (nSubIter > 1 && dtFull > SMALL) ? dtFull / nSubIter : dtFull;
    const scalar timeStart = (dtFull > SMALL) ? timeFull - dtFull : timeFull;
    const scalar tEffFull = computeTEff(cells, T);

    if (nSubIter > 1 && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< "ECM subIterations " << nSubIter
            << " with subDeltaT " << dtSub << " s" << nl;
    }

    const bool useAverage = (subIterationResult_ == "average");
    if (nSubIter > 1 && !useAverage && subIterationResult_ != "last")
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "Unknown subIterationResult '" << subIterationResult_
                << "', using average." << nl;
        }
    }

    HashTable<scalar, label> qByKeyAccum;
    label nOk = 0;

    auto runCouplingOnce = [&](const uint64_t stepId, const scalar timeValue, const scalar deltaT, HashTable<scalar, label>& qOut, uint64_t& outStep)
    {
        qOut.clear();
        outStep = 0;

        if (ioMode_ == "jsonWrapper")
        {
            if (!lumpedMode)
            {
                FatalErrorInFunction
                    << "ioMode=jsonWrapper requires couplingMode=lumped." << exit(FatalError);
            }

            // In masterGather parallel mode only master writes/reads files and
            // runs the Python subprocess.  Workers skip and receive the result
            // via the post-loop broadcast (same pattern as persistentPipe).
            if (masterGather && !Pstream::master() && Pstream::parRun())
            {
                outStep = stepId;
                return true;
            }

            const scalar TcellC = Tsend[0] + wrapperTempOffsetC_;
            scalar currentVal = lookupInputOrDefault("current_A", currentA_);
            currentVal = lookupInputOrDefault("current", currentVal);
            currentA_ = currentSign_ * currentVal;

            if (!writeWrapperJsonInput(TcellC, deltaT, timeValue, currentA_, stepId))
            {
                return false;
            }

            if (!runExternal())
            {
                return false;
            }

            scalar qOutVal = 0.0;
            scalar vT = 0.0;
            if (!readWrapperJsonOutput(qOutVal, vT))
            {
                return false;
            }

            qOut.insert(lumpedKey, qOutVal);
            outStep = stepId;
            return true;
        }

        if (ioMode_ == "persistentPipe")
        {
            if (lumpedMode)
            {
                if (masterGather && !Pstream::master() && Pstream::parRun())
                {
                    outStep = stepId;
                    return true; // qOut is filled by the master broadcast below
                }

                std::string reqJson;
                const scalar TcellC = Tsend[0] + wrapperTempOffsetC_;

                // DEBUG: Log the temperature value being sent
                if (Pstream::master() || !Pstream::parRun())
                {
                    Info<< "DEBUG: persistentPipe TcellC computation:"
                        << " Tsend[0]=" << Tsend[0]
                        << " wrapperTempOffsetC_=" << wrapperTempOffsetC_
                        << " TcellC=" << TcellC
                        << " isnan=" << std::isnan(TcellC)
                        << " isinf=" << std::isinf(TcellC) << nl;
                }

                scalar currentVal = lookupInputOrDefault("current_A", currentA_);
                currentVal = lookupInputOrDefault("current", currentVal);
                currentA_ = currentSign_ * currentVal;
                reqJson = buildWrapperRequestJson(TcellC, deltaT, timeValue, currentA_, stepId);

                // DEBUG: Write the exact JSON being sent to a file for inspection
                if (stepId <= 16010u)
                {
                    std::ofstream dbgfile("/tmp/ecm_req_json.txt", std::ios::app);
                    dbgfile << "Step " << stepId << ":\n" << reqJson.substr(0, 300) << "\n\n";
                    dbgfile.close();
                }

                std::string respJson;
                if (!callPersistentWrapper(reqJson, respJson))
                {
                    return false;
                }

                std::string status;
                if (!extractJsonString(respJson, "status", status))
                {
                    WarningInFunction
                        << "persistentPipe: missing status field in response" << nl;
                    return false;
                }
                if (status != "ok")
                {
                    std::string message;
                    if (!extractJsonString(respJson, "message", message)) message = "unknown";
                    WarningInFunction
                        << "persistentPipe: wrapper error: " << message << nl;
                    return false;
                }

                double qVal = 0.0;
                if (!extractJsonNumber(respJson, "Q_GEN_W", qVal))
                {
                    WarningInFunction
                        << "persistentPipe: missing Q_GEN_W in response" << nl;
                    return false;
                }

                qOut.insert(lumpedKey, static_cast<scalar>(qVal));
                outStep = stepId;
                return true;
            }

            // When element mapping active, workers skip ECM call;
            // master runs it and broadcasts result via the post-loop broadcast.
            if (hasElementMapping_ && masterGather && !Pstream::master() && Pstream::parRun())
            {
                outStep = stepId;
                return true; // qOut is empty; will be filled by broadcast
            }

            const std::string reqBinary =
                buildElementWisePipeRequestBinary(keys, Tsend, deltaT, timeValue, stepId, tEffFull);
            std::string respBinary;
            if (!callPersistentWrapperBinary(reqBinary, respBinary))
            {
                return false;
            }
            return parseOutputBuffer(respBinary, qOut, stepId, outStep);
        }

        if (ioMode_ == "cliWrapper")
        {
            if (!lumpedMode)
            {
                FatalErrorInFunction
                    << "ioMode=cliWrapper requires couplingMode=lumped." << exit(FatalError);
            }

            if (!wrapperWriteCsv_)
            {
                WarningInFunction
                    << "ioMode=cliWrapper requires wrapperWriteCsv=true to read Q_GEN output." << nl;
                return false;
            }

            const scalar TcellC = Tsend[0] + wrapperTempOffsetC_;
            scalar currentVal = lookupInputOrDefault("current_A", currentA_);
            currentVal = lookupInputOrDefault("current", currentVal);
            currentA_ = currentSign_ * currentVal;

            const string cmd = buildWrapperCommand(TcellC, deltaT);
            command_ = cmd;

            if (!runExternal())
            {
                return false;
            }

            scalar qOutVal = 0.0;
            scalar vT = 0.0;
            if (!readWrapperCsv(qOutVal, vT))
            {
                return false;
            }

            qOut.insert(lumpedKey, qOutVal);
            outStep = stepId;
            return true;
        }

        if (!writeInputWithTime(keys, Tsend, stepId, timeValue, deltaT))
        {
            return false;
        }

        if (!runExternal())
        {
            return false;
        }

        if (!readOutput(qOut, stepId, outStep))
        {
            return false;
        }

        return true;
    };

    for (label subIter = 0; subIter < nSubIter; ++subIter)
    {
        const scalar timeVal = (nSubIter > 1 && dtFull > SMALL)
            ? timeStart + (static_cast<scalar>(subIter) + 1.0) * dtSub
            : timeFull;
        const uint64_t stepIdSub = (nSubIter > 1)
            ? (static_cast<uint64_t>(stepId_) * static_cast<uint64_t>(nSubIter))
                + static_cast<uint64_t>(subIter) + 1u
            : stepId_;

        HashTable<scalar, label> qByKeySub;
        uint64_t outStepSub = 0;

        if (!runCouplingOnce(stepIdSub, timeVal, dtSub, qByKeySub, outStepSub))
        {
            outputOk = false;
            break;
        }

        nOk++;
        outStepId = outStepSub;

        if (nSubIter == 1 || subIterationResult_ == "last")
        {
            qByKey = qByKeySub;
            continue;
        }

        for
        (
            HashTable<scalar, label>::const_iterator iter = qByKeySub.cbegin();
            iter != qByKeySub.cend();
            ++iter
        )
        {
            const label key = iter.key();
            const scalar val = iter();
            HashTable<scalar, label>::iterator accIter = qByKeyAccum.find(key);
            if (accIter.found())
            {
                accIter() += val;
            }
            else
            {
                qByKeyAccum.insert(key, val);
            }
        }
    }

    if (outputOk && nSubIter > 1 && subIterationResult_ != "last")
    {
        if (nOk <= 0)
        {
            outputOk = false;
        }
        else
        {
            qByKey.clear();
            for
            (
                HashTable<scalar, label>::const_iterator iter = qByKeyAccum.cbegin();
                iter != qByKeyAccum.cend();
                ++iter
            )
            {
                qByKey.insert(iter.key(), iter() / static_cast<scalar>(nOk));
            }
        }
    }

    // Broadcast master-owned persistent-pipe results to workers.
    if ((lumpedMode || hasElementMapping_) && masterGather && Pstream::parRun())
    {
        label n = 0;
        List<label> kL;
        List<scalar> qL;
        if (Pstream::master())
        {
            n = static_cast<label>(qByKey.size());
            kL.setSize(n);
            qL.setSize(n);
            label i = 0;
            for
            (
                HashTable<scalar, label>::const_iterator it = qByKey.cbegin();
                it != qByKey.cend();
                ++it
            )
            {
                kL[i] = it.key();
                qL[i] = it();
                i++;
            }
        }
        Pstream::broadcast(n);
        kL.setSize(n);
        qL.setSize(n);
        Pstream::broadcast(kL);
        Pstream::broadcast(qL);
        if (!Pstream::master())
        {
            qByKey.clear();
            forAll(kL, i)
            {
                qByKey.insert(kL[i], qL[i]);
            }
        }
    }

    if (!outputOk)
    {
        missingOutputCount_++;

        if (missingOutputLimit_ > 0 && missingOutputCount_ >= missingOutputLimit_)
        {
            const bool isMaster = (Pstream::master() || !Pstream::parRun());
            if (missingOutputAction_ == "fatal")
            {
                FatalErrorInFunction
                    << "ECM output missing for " << missingOutputCount_
                    << " consecutive steps. Action=fatal." << exit(FatalError);
            }
            else if (missingOutputAction_ == "degraded")
            {
                if (!degradedMode_ && isMaster)
                {
                    WarningInFunction
                        << "ECM output missing for " << missingOutputCount_
                        << " consecutive steps. Entering degraded mode." << nl;
                }
                degradedMode_ = true;
            }
            else if (missingOutputAction_ != "warn")
            {
                if (isMaster)
                {
                    WarningInFunction
                        << "Unknown missingOutputAction '" << missingOutputAction_
                        << "'. Using warn behavior." << nl;
                }
            }
        }

        return true;
    }

    if (missingOutputCount_ > 0 && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< "ECM output recovered after " << missingOutputCount_
            << " missing steps." << nl;
    }
    missingOutputCount_ = 0;
    if (degradedMode_ && (Pstream::master() || !Pstream::parRun()))
    {
        Info<< "ECM degraded mode cleared." << nl;
    }
    degradedMode_ = false;

    auto integratedHeatFromMap =
    [&](const HashTable<scalar, label>& qMap) -> scalar
    {
        scalar qIntegrated = 0.0;
        if (lumpedMode)
        {
            scalar qOutVal = 0.0;
            HashTable<scalar, label>::const_iterator iter = qMap.find(lumpedKey);
            if (iter.found())
            {
                qOutVal = *iter;
            }
            else if (!qMap.empty())
            {
                qOutVal = qMap.begin()();
            }

            scalar qVol = qOutVal;
            if (lumpedOutput_ == "totalPower")
            {
                qVol = (totalVol > SMALL) ? qOutVal / (totalVol * totalVolumeScale_) : 0.0;
            }
            qIntegrated = qVol * totalVol;
        }
        else
        {
            const scalarField& V = mesh_.V();
            forAll(cells, i)
            {
                label lookupKey = keysLocal[i];
                if (hasElementMapping_)
                {
                    auto eIt = cellToEcmElement_.find(static_cast<int>(lookupKey));
                    if (eIt == cellToEcmElement_.end())
                    {
                        continue;
                    }
                    lookupKey = static_cast<label>(eIt->second);
                }

                HashTable<scalar, label>::const_iterator iter = qMap.find(lookupKey);
                if (iter.found())
                {
                    qIntegrated += (*iter) * V[cells[i]];
                }
            }
            reduce(qIntegrated, sumOp<scalar>());
        }
        return qIntegrated;
    };

    const scalar tEffNow = computeTEff(cells, T);
    const scalar qRaw = integratedHeatFromMap(qByKey);

    // Adaptive relaxation (optional)
    if (adaptiveRelaxation_)
    {
        const scalar qSumEstimate = qRaw;
        const scalar deltaT = mag(tEffNow - lastTEff_);
        const scalar deltaQ = mag(qSumEstimate - lastGoodQSum_);
        const bool spikeT = (deltaTThreshold_ > 0.0 && deltaT > deltaTThreshold_);
        const bool spikeQ = (deltaQThreshold_ > 0.0 && deltaQ > deltaQThreshold_);

        if (spikeT || spikeQ)
        {
            alpha_ = max(alphaMin_, alpha_ * (1.0 - alphaDecrease_));
        }
        else
        {
            alpha_ = min(alphaMax_, alpha_ + alphaIncrease_);
        }
        lastTEff_ = tEffNow;
    }
    else
    {
        alpha_ = relaxAlpha_;
    }

    // Basic sanity check: N mismatch warning, but proceed with key-based mapping
    label expectedN = 0;
    if (lumpedMode)
    {
        expectedN = 1;
    }
    else if (masterGather)
    {
        expectedN = (hasElementMapping_) ? nEcmElements_ : static_cast<label>(keys.size());
    }
    else
    {
        expectedN = keysLocal.size();
    }

    if (expectedN > 0 && static_cast<label>(qByKey.size()) != expectedN)
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "ECM output record count (" << qByKey.size()
                << ") does not match expected (" << expectedN
                << "). Proceeding with best-effort key mapping." << nl;
        }
    }

    HashTable<scalar, label> qByKeyApplied(qByKey);
    word temporalMode = temporalInterpolation_;
    if (temporalMode != "hold" && temporalMode != "linear")
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction
                << "Unknown temporalInterpolation '" << temporalInterpolation_
                << "'. Using hold behavior." << nl;
        }
        temporalMode = "hold";
    }

    if (temporalMode == "linear" && !lastGoodQByKey_.empty() && lastGoodStepId_ > 0)
    {
        typedef HashTable<scalar, label> QTable;
        forAllIter(QTable, qByKeyApplied, iter)
        {
            const label key = iter.key();
            const scalar currentVal = iter();
            const QTable::const_iterator prevIter = lastGoodQByKey_.find(key);
            const scalar prevVal = prevIter.found() ? prevIter() : currentVal;
            iter() = 0.5 * (currentVal + prevVal);
        }
    }

    const scalar qTarget = integratedHeatFromMap(qByKeyApplied);

    // Update fields for local cells
    scalar qSum = 0.0;
    if (lumpedMode)
    {
        qSum = updateFieldsLumped(cells, lumpedKey, qByKeyApplied);
    }
    else
    {
        qSum = updateFieldsElementWise(keysLocal, qByKeyApplied);
    }

    lastGoodStepId_ = outStepId;
    lastGoodTime_ = mesh_.time().value();
    lastGoodQSum_ = qSum;
    lastGoodQByKey_ = qByKeyApplied;

    if (!writeLastGoodSnapshot(qByKeyApplied, outStepId, lastGoodTime_, qSum, lastReturnCode_))
    {
        if (Pstream::master() || !Pstream::parRun())
        {
            WarningInFunction << "Failed to persist last-good ECM snapshot." << nl;
        }
    }

    if (Pstream::master() || !Pstream::parRun())
    {
        Info<< "ECM_heat_balance"
            << " step " << outStepId
            << " time " << mesh_.time().value()
            << " dt " << mesh_.time().deltaTValue()
            << " T_eff " << tEffNow
            << " q_raw " << qRaw
            << " q_target " << qTarget
            << " q_applied " << qSum
            << " alpha " << alpha_ << nl;
        Info<< "Q_sum_check " << qSum << " W" << nl;
        Info<< "alpha_used " << alpha_ << nl;
    }

    if
    (
        !appendHeatBalanceHistory
        (
            mesh_.time().value(),
            mesh_.time().deltaTValue(),
            outStepId,
            tEffNow,
            qRaw,
            qTarget,
            qSum
        )
     && (Pstream::master() || !Pstream::parRun())
    )
    {
        WarningInFunction << "Failed to append ECM heat-balance history." << nl;
    }

    persistIfWriteTime();

    return true;
}


bool ecmCoupler::write()
{
    if (!writeFields_)
    {
        return true;
    }

    // Fields are AUTO_WRITE; writing is handled by time object.
    // But functionObjects sometimes explicitly write here.
    fvMesh& mesh = const_cast<fvMesh&>(mesh_);

    if (mesh.foundObject<volScalarField>(qFieldName_))
    {
        mesh.lookupObjectRef<volScalarField>(qFieldName_).write();
    }

    if (outputMode_ == "temperatureSource" && mesh.foundObject<volScalarField>(stFieldName_))
    {
        mesh.lookupObjectRef<volScalarField>(stFieldName_).write();
    }

    return true;
}
