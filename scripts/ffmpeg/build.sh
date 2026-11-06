#!/usr/bin/env bash
# Reproduserbart, minimalt FFmpeg-bygg for Vestfold Media Converter.
#
# Kjøres på Ubuntu 24.04 (GitHub Actions eller en lokal maskin) og krysskompilerer
# statiske ffmpeg.exe/ffprobe.exe for 64-bit Windows. Alle kilder er låst i
# sources.json med SHA-256 eller git-commit. Resultatet er to arkiver i $OUT:
#
#   ffmpeg-vmc-<versjon>-win64.zip    programfiler, lisenser og BUILD-INFO.json
#   ffmpeg-vmc-<versjon>-source.tar   tilsvarende kildekode (GPL) for nøyaktig dette bygget
#
# Bygget har ingen nettverksstøtte og bare bibliotekene appen bruker.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${WORK:-$PWD/ffmpeg-work}"
SRC="$WORK/sources"
BUILD="$WORK/build"
export PREFIX="$WORK/prefix"
OUT="${OUT:-$PWD/ffmpeg-out}"
JOBS="$(nproc)"
HOST=x86_64-w64-mingw32
TOOLCHAIN="$HERE/mingw.cmake"

export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export CFLAGS="-O2 -pipe" CXXFLAGS="-O2 -pipe"
export LDFLAGS="-static -static-libgcc -static-libstdc++"

mkdir -p "$SRC" "$BUILD" "$PREFIX/include" "$PREFIX/lib/pkgconfig" "$OUT"

field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]].get(sys.argv[3], ""))' "$HERE/sources.json" "$1" "$2"; }
names() { python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))))' "$HERE/sources.json"; }

fetch() {
    local name="$1" file url sha git commit
    file="$(field "$name" file)"
    url="$(field "$name" url)"
    sha="$(field "$name" sha256)"
    git="$(field "$name" git)"
    commit="$(field "$name" commit)"
    if [[ -n "$git" ]]; then
        if [[ ! -f "$SRC/$file" ]]; then
            local clone="$WORK/git-$name"
            rm -rf "$clone"
            git clone --quiet --filter=blob:none "$git" "$clone"
            git -C "$clone" checkout --quiet "$commit"
            [[ "$(git -C "$clone" rev-parse HEAD)" == "$commit" ]] || { echo "Feil commit for $name" >&2; exit 1; }
            git -C "$clone" archive --format=tar.gz --prefix="$(field "$name" dir)/" -o "$SRC/$file" HEAD
        fi
    else
        [[ -f "$SRC/$file" ]] || curl -fsSL --retry 5 --retry-delay 5 -o "$SRC/$file" "$url"
        echo "$sha  $SRC/$file" | sha256sum -c --quiet - || { echo "Feil SHA-256 for $name" >&2; exit 1; }
    fi
    rm -rf "$BUILD/$(field "$name" dir)"
    tar -xf "$SRC/$file" -C "$BUILD"
}

srcdir() { echo "$BUILD/$(field "$1" dir)"; }
cmake_build() {
    local source="$1" build="$2"; shift 2
    cmake -S "$source" -B "$build" -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "$@"
    cmake --build "$build" -j "$JOBS"
}
autotools() {
    ./configure --host="$HOST" --prefix="$PREFIX" --disable-shared --enable-static "$@"
    make -j "$JOBS"
    make install
}

for name in $(names); do fetch "$name"; done

# Komprimering, brukt av blant annet PNG, TIFF og komprimerte MKV-spor.
(cd "$(srcdir zlib)" && make -f win32/Makefile.gcc PREFIX="$HOST-" -j "$JOBS" libz.a &&
    cp zlib.h zconf.h "$PREFIX/include/" && cp libz.a "$PREFIX/lib/")
(cd "$(srcdir bzip2)" && make CC="$HOST-gcc" AR="$HOST-ar" RANLIB="$HOST-ranlib" CFLAGS="$CFLAGS -D_FILE_OFFSET_BITS=64" -j "$JOBS" libbz2.a &&
    cp bzlib.h "$PREFIX/include/" && cp libbz2.a "$PREFIX/lib/")
(cd "$(srcdir xz)" && autotools --disable-xz --disable-xzdec --disable-lzmadec --disable-lzmainfo \
    --disable-lzma-links --disable-scripts --disable-doc --disable-nls)

# Lyd.
(cd "$(srcdir libogg)" && autotools)
(cd "$(srcdir libvorbis)" && sed -i 's/-mno-ieee-fp//g' configure &&
    autotools --with-ogg="$PREFIX" --disable-docs --disable-examples --disable-oggtest)
(cd "$(srcdir opus)" && autotools --disable-doc --disable-extra-programs --disable-stack-protector)
(cd "$(srcdir lame)" && sed -i '/lame_init_old/d' include/libmp3lame.sym &&
    autotools --disable-frontend --disable-decoder --disable-gtktest)

# Video.
(cd "$(srcdir x264)" && ./configure --host="$HOST" --cross-prefix="$HOST-" --prefix="$PREFIX" \
    --enable-static --enable-pic --disable-cli --disable-lavf --disable-swscale --disable-ffms \
    --disable-gpac --disable-lsmash --bit-depth=all && make -j "$JOBS" && make install)

# x265 med 8-, 10- og 12-bit i ett bibliotek, slik at 10-bit HEVC fortsatt kan velges.
X265="$(srcdir x265)/source"
cmake_build "$X265" "$BUILD/x265-12" -DHIGH_BIT_DEPTH=ON -DMAIN12=ON -DEXPORT_C_API=OFF \
    -DENABLE_SHARED=OFF -DENABLE_CLI=OFF
cmake_build "$X265" "$BUILD/x265-10" -DHIGH_BIT_DEPTH=ON -DEXPORT_C_API=OFF \
    -DENABLE_SHARED=OFF -DENABLE_CLI=OFF
mkdir -p "$BUILD/x265-8"
cp "$BUILD/x265-10/libx265.a" "$BUILD/x265-8/libx265_main10.a"
cp "$BUILD/x265-12/libx265.a" "$BUILD/x265-8/libx265_main12.a"
cmake_build "$X265" "$BUILD/x265-8" -DEXTRA_LIB="x265_main10.a;x265_main12.a" -DEXTRA_LINK_FLAGS=-L. \
    -DLINKED_10BIT=ON -DLINKED_12BIT=ON -DENABLE_SHARED=OFF -DENABLE_CLI=OFF
cmake --install "$BUILD/x265-8"
"$HOST-ar" -M <<EOF
CREATE $PREFIX/lib/libx265.a
ADDLIB $BUILD/x265-8/libx265.a
ADDLIB $BUILD/x265-8/libx265_main10.a
ADDLIB $BUILD/x265-8/libx265_main12.a
SAVE
END
EOF
"$HOST-ranlib" "$PREFIX/lib/libx265.a"
sed -i -e 's/-lgcc_s//g' -e 's/^Libs.private:.*/Libs.private: -lstdc++ -lwinpthread/' "$PREFIX/lib/pkgconfig/x265.pc"

AOM="$(srcdir libaom)"
cmake -S "$AOM" -B "$BUILD/aom" -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$AOM/cmake/toolchains/x86_64-mingw-gcc.cmake" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DBUILD_SHARED_LIBS=0 -DENABLE_TESTS=0 -DENABLE_TESTDATA=0 -DENABLE_EXAMPLES=0 -DENABLE_DOCS=0 \
    -DENABLE_TOOLS=0 -DCONFIG_RUNTIME_CPU_DETECT=1
cmake --build "$BUILD/aom" -j "$JOBS"
cmake --install "$BUILD/aom"

(cd "$(srcdir libvpx)" && CROSS="$HOST-" ./configure --target=x86_64-win64-gcc --prefix="$PREFIX" \
    --disable-examples --disable-tools --disable-docs --disable-unit-tests --enable-vp9-highbitdepth \
    --disable-shared --enable-static --enable-runtime-cpu-detect && make -j "$JOBS" && make install)

# Valgfrie GPU-encodere. Bare headere og Intels dispatcher; driverne følger med Windows/GPU.
make -C "$(srcdir nv-codec-headers)" PREFIX="$PREFIX" install
mkdir -p "$PREFIX/include/AMF"
cp -r "$(srcdir amf-headers)/AMF/." "$PREFIX/include/AMF/"
cmake_build "$(srcdir libvpl)" "$BUILD/vpl" -DBUILD_SHARED_LIBS=OFF -DBUILD_TOOLS=OFF -DBUILD_EXAMPLES=OFF \
    -DBUILD_TESTS=OFF -DINSTALL_EXAMPLES=OFF -DBUILD_EXPERIMENTAL=OFF
cmake --install "$BUILD/vpl"

# FFmpeg uten nettverk, ffplay, enheter (unntatt lavfi) eller automatisk oppdagede biblioteker.
FFMPEG_FLAGS=(
    --enable-gpl --enable-version3 --disable-autodetect --disable-network --disable-ffplay
    --disable-doc --disable-debug --disable-indevs --enable-indev=lavfi --disable-outdevs --disable-protocol=prompeg
    --enable-w32threads --enable-zlib --enable-bzlib --enable-lzma
    --enable-libx264 --enable-libx265 --enable-libaom --enable-libvpx
    --enable-libmp3lame --enable-libopus --enable-libvorbis
    --enable-ffnvcodec --enable-nvenc --enable-nvdec --enable-cuvid --enable-amf --enable-libvpl
    --enable-dxva2 --enable-d3d11va
)
FFMPEG="$(srcdir ffmpeg)"
(cd "$FFMPEG" && ./configure --prefix="$WORK/ffmpeg" --target-os=mingw32 --arch=x86_64 \
    --cross-prefix="$HOST-" --pkg-config=pkg-config --pkg-config-flags=--static \
    --extra-version=vmc --extra-cflags="-I$PREFIX/include -DLZMA_API_STATIC" \
    --extra-ldflags="-L$PREFIX/lib $LDFLAGS" --extra-libs="-lstdc++ -lwinpthread" \
    "${FFMPEG_FLAGS[@]}" && make -j "$JOBS" && make install)

# Pakk programfiler, lisenser og byggbeskrivelse.
VERSION="$(field ffmpeg version)"
PACKAGE="$OUT/ffmpeg-vmc-$VERSION-win64"
rm -rf "$PACKAGE" && mkdir -p "$PACKAGE/bin" "$PACKAGE/licenses"
cp "$WORK/ffmpeg/bin/ffmpeg.exe" "$WORK/ffmpeg/bin/ffprobe.exe" "$PACKAGE/bin/"
cp "$FFMPEG/COPYING.GPLv3" "$PACKAGE/LICENSE.txt"
for name in $(names); do
    target="$PACKAGE/licenses/$name"
    mkdir -p "$target"
    find "$(srcdir "$name")" -maxdepth 1 -type f \( -iname 'COPYING*' -o -iname 'LICENSE*' -o -iname 'PATENTS*' \
        -o -iname 'NOTICE*' \) -exec cp {} "$target/" \;
done
# AMF og nv-codec-headers har MIT-teksten øverst i headerne, ikke i en egen fil.
sed -n '1,/\*\//p' "$(srcdir amf-headers)/AMF/core/Factory.h" > "$PACKAGE/licenses/amf-headers/LICENSE-from-header.txt"
sed -n '1,/\*\//p' "$(srcdir nv-codec-headers)/include/ffnvcodec/nvEncodeAPI.h" \
    > "$PACKAGE/licenses/nv-codec-headers/LICENSE-from-header.txt"
for doc in mingw-w64-common mingw-w64-x86-64-dev gcc-mingw-w64-base; do
    [[ -f "/usr/share/doc/$doc/copyright" ]] && cp "/usr/share/doc/$doc/copyright" "$PACKAGE/licenses/toolchain-$doc.txt"
done

TOOLCHAIN_VERSIONS="$(dpkg-query -W -f='${Package} ${Version}\n' 'gcc-mingw-w64*' 'g++-mingw-w64*' \
    'binutils-mingw-w64*' 'mingw-w64*' nasm cmake 2>/dev/null || true)"
python3 - "$HERE/sources.json" "$PACKAGE/BUILD-INFO.json" "$TOOLCHAIN_VERSIONS" "${FFMPEG_FLAGS[*]}" <<'PY'
import json, platform, sys
sources, target, toolchain, flags = sys.argv[1:5]
info = {
    "provider": "vmc",
    "description": "Minimalt FFmpeg-bygg for Vestfold Media Converter. Ingen nettverksstøtte.",
    "ffmpeg_version": json.load(open(sources))["ffmpeg"]["version"],
    "configure_flags": flags.split(),
    "components": json.load(open(sources)),
    "build_host": platform.platform(),
    "toolchain": [line for line in toolchain.splitlines() if line.strip()],
}
json.dump(info, open(target, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
(cd "$PACKAGE" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum | sed 's#  \./#  #' > SHA256SUMS.txt)
(cd "$OUT" && rm -f "$(basename "$PACKAGE").zip" && zip -qr "$(basename "$PACKAGE").zip" "$(basename "$PACKAGE")")

# Tilsvarende kildekode: alle kildearkiv, byggoppskriften og verktøykjedens versjoner.
SOURCE="$OUT/ffmpeg-vmc-$VERSION-source"
rm -rf "$SOURCE" && mkdir -p "$SOURCE/sources" "$SOURCE/recipe"
cp "$SRC"/* "$SOURCE/sources/"
cp "$HERE"/* "$SOURCE/recipe/"
cp "$PACKAGE/BUILD-INFO.json" "$SOURCE/"
cat > "$SOURCE/README.txt" <<EOF
Tilsvarende kildekode for ffmpeg.exe og ffprobe.exe i Vestfold Media Converter.

sources/   Uendrede kildearkiv for FFmpeg $VERSION og alle bibliotekene som er lenket inn.
recipe/    Byggskriptet (build.sh), CMake-verktøykjeden og sources.json med SHA-256/commit.

Bygg på nytt på Ubuntu 24.04 med pakkene i BUILD-INFO.json ("toolchain"):
  WORK=\$PWD/work OUT=\$PWD/out bash recipe/build.sh
Legg kildearkivene i work/sources/ først for å bygge uten nett.
EOF
tar -cf "$SOURCE.tar" -C "$OUT" "$(basename "$SOURCE")"
rm -rf "$SOURCE"
ls -la "$OUT"
