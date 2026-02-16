desktop_conf = configuration_data()
desktop_conf.set('bindir', get_option('prefix') / get_option('bindir'))

configure_file(
  input: 'io.github.photogrid.desktop.in',
  output: 'io.github.photogrid.desktop',
  configuration: desktop_conf,
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

install_data(
  'io.github.photogrid.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)
