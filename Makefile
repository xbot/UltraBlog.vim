PLUGIN = UltraBlog

SOURCE = plugin/UltraBlog.vim
SOURCE += doc/UltraBlog.txt
SOURCE += plugin/ultrablog/__init__.py
SOURCE += plugin/ultrablog/commands.py
SOURCE += plugin/ultrablog/db.py
SOURCE += plugin/ultrablog/eventqueue.py
SOURCE += plugin/ultrablog/events.py
SOURCE += plugin/ultrablog/exceptions.py
SOURCE += plugin/ultrablog/listeners.py
SOURCE += plugin/ultrablog/util.py

${PLUGIN}.vmb: ${SOURCE}
	vim --cmd 'let g:plugin_name="${PLUGIN}"' -s build.vim

install:
	rsync -Rv ${SOURCE} ${HOME}/.vim/

clean:
	rm ${PLUGIN}.vmb
