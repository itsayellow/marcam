.PHONY: clean app dmg
clean:
	rm -rf build dist virt

app: dist/Cellcounter.app

dmg: dist/Cellcounter.dmg

virt:
	./gen_virt

dist/Cellcounter.app: cellcounter/* virt
	./gen_app

dist/Cellcounter.dmg: dist/Cellcounter.app
	./gen_dmg

# vim: nowrap noexpandtab sw=8
