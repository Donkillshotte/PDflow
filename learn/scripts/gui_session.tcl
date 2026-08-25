# Load an ODB and prepare the Qt GUI for screenshots.
# Requires: ODB_FILE, optional GUI_VIEW = {all,pdn,clock,signal,instances,rows}
set odb $::env(ODB_FILE)
puts "GUI_SESSION loading $odb"
read_db $odb

proc or_gui_apply_view {} {
  set view "all"
  if { [info exists ::env(GUI_VIEW)] } {
    set view $::env(GUI_VIEW)
  }
  puts "GUI_VIEW=$view"
  catch { gui::set_display_controls "Layers/*" visible true }
  catch { gui::set_display_controls "Nets/*" visible true }
  catch { gui::set_display_controls "Instances/*" visible true }
  catch { gui::set_display_controls "Rows" visible true }
  if { $view eq "pdn" } {
    catch { gui::set_display_controls "Nets/Signal" visible false }
    catch { gui::set_display_controls "Nets/Clock" visible false }
    catch { gui::set_display_controls "Instances/StdCells" visible false }
  } elseif { $view eq "clock" } {
    catch { gui::set_display_controls "Nets/Signal" visible false }
    catch { gui::set_display_controls "Nets/Power" visible false }
    catch { gui::set_display_controls "Nets/Ground" visible false }
    catch { gui::set_display_controls "Nets/Clock" visible true }
  } elseif { $view eq "signal" } {
    catch { gui::set_display_controls "Nets/Clock" visible false }
    catch { gui::set_display_controls "Nets/Power" visible false }
    catch { gui::set_display_controls "Nets/Ground" visible false }
  } elseif { $view eq "instances" } {
    catch { gui::set_display_controls "Nets/*" visible false }
    catch { gui::set_display_controls "Layers/*" visible false }
    catch { gui::set_display_controls "Instances/*" visible true }
    catch { gui::set_display_controls "Rows" visible true }
  } elseif { $view eq "rows" } {
    catch { gui::set_display_controls "Nets/*" visible false }
    catch { gui::set_display_controls "Instances/*" visible false }
    catch { gui::set_display_controls "Layers/*" visible false }
    catch { gui::set_display_controls "Rows" visible true }
  }
  catch { gui::fit }
  puts "GUI_READY"
}

# GUI widgets exist only after the Qt event loop starts (after this script returns).
after 1500 or_gui_apply_view
