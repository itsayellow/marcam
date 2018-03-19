.PHONY: clean clean_all app dmg
clean:
	rm -rf build dist

clean_all:
	rm -rf build dist virt

app: dist/Marcam.app

dmg: dist/Marcam.dmg

exe: dist/marcam/Marcam.exe

virt: requirements.txt
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

# vim: nowrap noexpandtab sw=8 sts=0
