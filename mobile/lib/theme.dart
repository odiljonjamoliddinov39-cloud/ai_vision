import 'package:flutter/material.dart';

class AppColors {
  static const blue = Color(0xFF2188FF);
  static const cyan = Color(0xFF4CCBFF);
  static const green = Color(0xFF35D58D);
  static const amber = Color(0xFFFFB23F);
  static const red = Color(0xFFFF5252);
  static const purple = Color(0xFF8B6CFF);
  static const navy = Color(0xFF07131F);
  static const navySoft = Color(0xFF0D1B28);
  static const panel = Color(0xFF122231);
  static const line = Color(0xFF24394A);
}

class AppTheme {
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData light() => _build(Brightness.light);

  static ThemeData _build(Brightness brightness) {
    final dark = brightness == Brightness.dark;
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.blue,
      brightness: brightness,
      primary: AppColors.blue,
      secondary: AppColors.cyan,
      surface: dark ? AppColors.navySoft : const Color(0xFFF4F8FC),
      error: AppColors.red,
    );

    final border = dark ? AppColors.line : const Color(0xFFD9E4EE);
    final card = dark ? AppColors.panel : Colors.white;

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: dark ? AppColors.navy : const Color(0xFFEDF3F8),
      canvasColor: dark ? AppColors.navySoft : Colors.white,
      cardColor: card,
      dividerColor: border,
      fontFamily: 'Roboto',
      appBarTheme: AppBarTheme(
        backgroundColor: dark ? AppColors.navy : Colors.white,
        foregroundColor: dark ? Colors.white : const Color(0xFF14293B),
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: dark ? Colors.white : const Color(0xFF14293B),
          fontWeight: FontWeight.w700,
          fontSize: 19,
        ),
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: dark ? 0 : 1.5,
        shadowColor: Colors.black.withValues(alpha: .10),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: border),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 70,
        backgroundColor: dark ? const Color(0xFF091722) : Colors.white,
        indicatorColor: AppColors.blue.withValues(alpha: .18),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            fontSize: 11,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
            color: states.contains(WidgetState.selected)
                ? AppColors.blue
                : (dark ? const Color(0xFF91A2B1) : const Color(0xFF607285)),
          ),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: dark ? const Color(0xFF091722) : Colors.white,
        indicatorColor: AppColors.blue.withValues(alpha: .18),
        selectedIconTheme: const IconThemeData(color: AppColors.blue),
        selectedLabelTextStyle: const TextStyle(
          color: AppColors.blue,
          fontWeight: FontWeight.w700,
        ),
      ),
      drawerTheme: DrawerThemeData(
        backgroundColor: dark ? const Color(0xFF091722) : Colors.white,
        shape: const RoundedRectangleBorder(),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: dark ? const Color(0xFF0B1925) : const Color(0xFFF6F9FC),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.blue, width: 1.5),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.blue,
          foregroundColor: Colors.white,
          minimumSize: const Size(120, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: dark ? Colors.white : const Color(0xFF183044),
          side: BorderSide(color: border),
          minimumSize: const Size(120, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: card,
        selectedColor: AppColors.blue,
        side: BorderSide(color: border),
        labelStyle: TextStyle(
          color: dark ? Colors.white : const Color(0xFF183044),
        ),
        secondaryLabelStyle: const TextStyle(color: Colors.white),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.selected) ? Colors.white : null,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.selected) ? AppColors.cyan : null,
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.blue,
      ),
    );
  }
}

class ThemeController extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.dark;

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  void toggle() {
    _mode = isDark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }
}
