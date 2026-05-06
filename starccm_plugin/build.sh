#!/bin/bash
# Build EcmCouplerMacro for STAR-CCM+ 21.02
# Produces dist/EcmCouplerMacro.jar
#
# STAR-CCM+ 21.02 (Windows install) is mounted at /opt/starccm.
# The actual API classes live in starbase.jar (not star-coremodule.jar).
# Compiler: javac 21 from conda env java21.

JAVA_HOME="/home/helios/.conda/envs/java21"
JAVAC="$JAVA_HOME/bin/javac"
JAR_CMD="$JAVA_HOME/bin/jar"

# /opt/starccm is the Windows STAR-CCM+ 21.02.008 install (read-only Linux mount)
STAR_LIB="/opt/starccm/star/lib/java/platform"
STAR_JAR="$STAR_LIB/modules/ext/starbase.jar"   # contains star.common.*, star.base.*, etc.
NB_LIB="$STAR_LIB/lib"

CLASSPATH="$STAR_JAR:$NB_LIB/org-openide-util.jar:$NB_LIB/org-openide-modules.jar"

SRC="src"
BUILD="build/classes"
DIST="dist"

mkdir -p "$BUILD" "$DIST"

echo "Compiling..."
"$JAVAC" -source 11 -target 11 \
  -cp "$CLASSPATH" \
  -d "$BUILD" \
  "$SRC/EcmBinaryIO.java" \
  "$SRC/EcmCouplerMacro.java"

if [ $? -ne 0 ]; then
  echo "Compilation failed."
  exit 1
fi

echo "Packaging..."
"$JAR_CMD" cf "$DIST/EcmCouplerMacro.jar" -C "$BUILD" .

echo "Done: $DIST/EcmCouplerMacro.jar"
