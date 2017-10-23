.PHONY: clean
clean:
	rm -rf build dist virt

virt:
	./gen_virt

dist/Cellcounter.app: cellcounter/* virt
	./gen_app
