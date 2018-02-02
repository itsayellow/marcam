.PHONY: clean clean_all app dmg
clean:
	rm -rf build dist

clean_all:
	rm -rf build dist virt

app: dist/Cellcounter.app

dmg: dist/Cellcounter.dmg

virt: requirements.txt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make virtual environment"
	@echo ""
	rm -rf virt
	./build_scripts/gen_virt

dist/Cellcounter.app: cellcounter/* virt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make app"
	@echo ""
	./build_scripts/gen_app

dist/Cellcounter.dmg: dist/Cellcounter.app
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make dmg"
	@echo ""
	./build_scripts/gen_dmg

# vim: nowrap noexpandtab sw=8 sts=0
