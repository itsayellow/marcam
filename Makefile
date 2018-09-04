.PHONY: clean clean_all tests
clean:
	rm -rf build dist

clean_all:
	rm -rf build dist virt virt_test

app: dist/Marcam.app

dmg: dist/Marcam.dmg

exe: dist/marcam/Marcam.exe

wininstall: dist/Marcam_Installer.exe

tests: virt_test tests/*
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Execute tests"
	@echo ""
	./build_scripts/do_tests

virt_test: requirements_test.txt requirements.txt requirements_mac.txt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make virtual test environment"
	@echo ""
	rm -rf virt_test
	./build_scripts/gen_virt_test

virt: requirements.txt requirements_mac.txt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make virtual environment"
	@echo ""
	rm -rf virt
	./build_scripts/gen_virt

dist/Marcam.app: marcam/* virt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make app (MacOS)"
	@echo ""
	./build_scripts/gen_app

dist/Marcam.dmg: dist/Marcam.app
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make dmg (MacOS)"
	@echo ""
	./build_scripts/gen_dmg

dist/marcam/Marcam.exe: marcam/* virt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make exe (Windows)"
	@echo ""
	./build_scripts/gen_winexe

dist/Marcam_Installer.exe: dist/marcam/Marcam.exe
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make installer (Windows)"
	@echo ""
	./build_scripts/gen_wininstaller

# vim: nowrap noexpandtab sw=8 sts=0
