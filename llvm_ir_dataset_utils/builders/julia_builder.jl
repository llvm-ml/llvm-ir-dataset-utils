"""
Calling convention: julia julia_builder.jl <package name>
After which you receive the system image, and a bitcode
  archive which is to be unpacked with `ar -x`.
"""

using Pkg;

# Install PackageCompiler.jl
Pkg.add("PackageCompiler");
using PackageCompiler;

# Rope in the ARGS given to Julia
for x in ARGS
    
    # Adding the Julia package
    try
        Pkg.add(x);
        using x;
    catch e
        # line is buggy rn and just prints whenever
        # Error given when triggered alone: 
        #   TypeError: in using, expected Symbol, got a value of type Core.SlotNumber
        println("Package not found.");
    end

    # Assemble the storage strings
    sys_img_name = "SysImage.so";

    # Compile the system image, and the bitcode
    create_sysimage(
        [x];
        sysimage_path=sys_img_name,
        sysimage_build_args=`--output-bc bitcode.a`
    )

end
