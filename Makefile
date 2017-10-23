.PHONY: clean app dmg
clean:
	rm -rf build dist virt

app: dist/Cellcounter.app

dmg: dist/Cellcounter.dmg

virt: requirements.txt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make virtual environment"
	@echo ""
	rm -rf virt
	./gen_virt

dist/Cellcounter.app: cellcounter/* virt
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make app"
	@echo ""
	./gen_app

dist/Cellcounter.dmg: dist/Cellcounter.app
	@echo ""
	@echo "---------------------------------------------------------------"
	@echo "Make dmg"
	@echo ""
	./gen_dmg

# vim: nowrap noexpandtab sw=8 sts=0
