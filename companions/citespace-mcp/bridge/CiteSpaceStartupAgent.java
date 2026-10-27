import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.InputStream;
import java.util.*;
import javax.swing.*;

/** Narrow, local startup adapter. No bytecode changes, network or license edits. */
public final class CiteSpaceStartupAgent {
    private static Path directory;
    public static void premain(String options, Instrumentation ignored) {
        directory = Paths.get(options);
        Thread thread = new Thread(new Runnable() {
            public void run() {
                while (true) {
                    try {
                        Files.createDirectories(directory);
                        try (DirectoryStream<Path> stream = Files.newDirectoryStream(directory, "*.request")) {
                            for (Path request : stream) process(request);
                        }
                        Thread.sleep(100);
                    } catch (InterruptedException e) { return; }
                    catch (Exception e) {
                        try { Thread.sleep(300); } catch (InterruptedException x) { return; }
                    }
                }
            }
        }, "citespace-mcp-startup");
        thread.setDaemon(true);
        thread.start();
    }
    private static void flatten(Component c, List<Component> out) {
        out.add(c);
        if (c instanceof Container) for (Component child : ((Container)c).getComponents()) flatten(child, out);
    }
    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", "\\r").replace("\n", "\\n");
    }
    private static String execute(String action) {
        List<JDialog> dialogs = new ArrayList<JDialog>();
        for (Window window : Window.getWindows()) {
            if (window instanceof JDialog && window.isShowing() && "Validation".equals(((JDialog)window).getTitle())) dialogs.add((JDialog)window);
        }
        if (dialogs.size()!=1) throw new IllegalStateException("Expected exactly one visible Validation dialog");
        JDialog dialog = dialogs.get(0);
        List<Component> components = new ArrayList<Component>(); flatten(dialog, components);
        List<JTextField> fields = new ArrayList<JTextField>();
        List<JButton> buttons = new ArrayList<JButton>();
        for (Component c : components) {
            if (c instanceof JTextField && !(c instanceof JPasswordField) && c.isShowing() && ((JTextField)c).isEditable()) fields.add((JTextField)c);
            if (c instanceof JButton && c.isShowing() && c.isEnabled()) buttons.add((JButton)c);
        }
        JButton button = dialog.getRootPane().getDefaultButton();
        if (button==null && buttons.size()==1) button=buttons.get(0);
        if (button==null || !button.isEnabled()) throw new IllegalStateException("No unambiguous enabled default button");
        if ("email".equals(action)) {
            if (fields.size()!=1) throw new IllegalStateException("Email dialog must have one editable field");
            fields.get(0).setText("citespace-mcp-test@example.invalid");
        } else if ("confirm".equals(action)) {
            if (fields.size()!=0) throw new IllegalStateException("Confirmation must not have an editable field");
        } else throw new IllegalArgumentException("Unsupported startup action");
        final JButton chosen = button;
        // A click can open another modal dialog. Queue it on the EDT and keep
        // the adapter thread available for the next separately verified action.
        SwingUtilities.invokeLater(new Runnable() { public void run() { chosen.doClick(); } });
        return "{\"ok\":true,\"action_requested\":true,\"action\":\""+action+"\",\"transport\":\"Swing EDT setText/doClick\",\"pid\":\""+
            ManagementFactory.getRuntimeMXBean().getName().split("@")[0]+"\"}";
    }
    private static void process(Path request) throws Exception {
        final Path processing=request.resolveSibling(request.getFileName().toString()+".processing");
        Files.move(request,processing);
        Properties properties=new Properties();
        try (InputStream input=Files.newInputStream(processing)) { properties.load(input); }
        final String action=properties.getProperty("action", "");
        final String[] response=new String[1];
        SwingUtilities.invokeAndWait(new Runnable() {
            public void run() {
                try { response[0]=execute(action); }
                catch (Exception e) { response[0]="{\"ok\":false,\"error\":\""+escape(e.toString())+"\"}"; }
            }
        });
        Path reply=request.resolveSibling(request.getFileName().toString().replace(".request",".reply.json"));
        Path temp=reply.resolveSibling(reply.getFileName().toString()+".tmp");
        Files.write(temp,response[0].getBytes(StandardCharsets.UTF_8));
        Files.move(temp,reply,StandardCopyOption.ATOMIC_MOVE);
    }
}
