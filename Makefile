.PHONY: clean clean_all app dmg
clean:
	rm -rf build dist

clean_all:
	rm -rf build dist virt

app: dist/Marcam.app

dmg: dist/Marcam.dmg

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
	@echo "Make app"
	@echo ""
	./build_scripts/gen_app

dist/Marcam.dmg: dist/Marcam.app
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make dmg"
	@echo ""
	./build_scripts/gen_dmg

# vim: nowrap noexpandtab sw=8 sts=0
