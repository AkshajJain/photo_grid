conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'photo-grid.in',
  output: 'photo-grid',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_data(
  'photo_grid.py',
  install_dir: pkgdatadir,
)
