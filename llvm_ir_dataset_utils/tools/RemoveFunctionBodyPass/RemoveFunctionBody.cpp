#include <llvm/Config/llvm-config-x86_64.h>
#include <llvm/IR/PassManager.h>
#include <llvm/IR/Value.h>
#include <llvm/Support/Compiler.h>

#include "llvm/IR/LegacyPassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/CommandLine.h"
using namespace llvm;
using namespace std;

namespace {
cl::list<int> Lists("index", cl::desc("Specify function index"), cl::OneOrMore);
struct RemoveFunctionBodyPass : PassInfoMixin<RemoveFunctionBodyPass> {
  PreservedAnalyses run(Module &M, ModuleAnalysisManager &MAM) {
    if (Lists.size() != 1) {
      errs() << "There should be only 1 argument!\n";
      return PreservedAnalyses::all();
    }

    int Index = -2;
    for (auto arg : Lists) {
      Index = arg;
    }
    int n_funcs = M.getFunctionList().size();
    if (Index == -1) {
      errs() << "n=" << n_funcs << '\n';
      return PreservedAnalyses::all();
    }
    if (Index >= n_funcs || Index < -1) {
      errs() << "Index is out of range! "
             << "Index=" << Index << " n=" << n_funcs << "\n";
      return PreservedAnalyses::all();
    }

    int count = -1;
    for (Function &F : M) {
      Function *fp = &F;
      if (count == Index - 1) {
        if (fp->isDeclaration()) {
          return PreservedAnalyses::all();
        }
        std::vector<Use *> useList;
        for (auto &use : fp->uses()) {
          useList.push_back(&use);
        }
        for (auto &use : useList) {
          if (isa<GlobalAlias>(use->getUser())) {
            GlobalAlias *ga = cast<GlobalAlias>(use->getUser());
            ga->replaceAllUsesWith(fp);
            ga->eraseFromParent();
          }
        }
        fp->deleteBody();
        fp->setComdat(NULL);
      }
      count++;
    }
    return PreservedAnalyses::none();
  }
};
} // namespace

/* New PM Registration */
llvm::PassPluginLibraryInfo getRemoveFunctionBodyPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "RemoveFunctionBody", LLVM_VERSION_STRING,
          [](PassBuilder &PB) {
            PB.registerPipelineParsingCallback(
                [](StringRef Name, llvm::ModulePassManager &MPM,
                   ArrayRef<llvm::PassBuilder::PipelineElement>) {
                  if (Name == "remove-fn-body") {
                    MPM.addPass(RemoveFunctionBodyPass());
                    return true;
                  }
                  return false;
                });
          }};
}

// Core interface for pass plugins. To guarantee 'opt'
// will be able to recognize the pass
extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
llvmGetPassPluginInfo() {
  return getRemoveFunctionBodyPluginInfo();
}
