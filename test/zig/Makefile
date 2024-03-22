# Environment variables
ZIG_PATH ?= /opt/homebrew/bin/zig

# Testing
UNOPT_BITCODE ?= no
UNOPT_LLVM_IR ?= no
OPT_BITCODE ?= no
OPT_LLVM_IR ?= no

ZIGC := $(ZIG_PATH)
ZIGFLAGS = build-exe

# Syntax to emit file: --verbose-llvm-bc=<filename>.bc
ifeq ($(UNOPT_BITCODE), yes)
	ZIGFLAGS += --verbose-llvm-bc
endif

# Syntax to emit file: --verbose-llvm-ll=<filename>.ll
ifeq ($(UNOPT_LLVM_IR), yes)
	ZIGFLAGS += --verbose-llvm-ir
endif

# Syntax to emit file: -femit-llvm-bc=<filename>.bc
ifeq ($(OPT_BITCODE), yes)
	ZIGFLAGS += -femit-llvm-bc
endif

# Syntax to emit file: -femit-llvm-ir=<filename>.ll
ifeq ($(OPT_LLVM_IR), yes)
	ZIGFLAGS += -femit-llvm-ir
endif

all: release

release: hello

hello: hello.zig
	$(ZIGC) $(ZIGFLAGS) $<

clean:
	rm -rf hello hello.bc hello.o hello.ll