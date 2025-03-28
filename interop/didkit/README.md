# DIDKit Python Wrapper

This is a quick python wrapper for a fork of DIDKit. It only defines the `verify_credential` function.

To use this wrapper:
- Build the fork of DIDKit for your system (e.g. `cargo build` in the `lib` directory)
- Copy the `libdidkit.so` to the same directory as this wrapper
- You can run a quick static test by invoking the wrapper script `python wrapper.py`
- `contexts.py` also needs to be in the same directory for the static test
- You can use a rust aware debugger such as `rust-gdb` to step through execution
