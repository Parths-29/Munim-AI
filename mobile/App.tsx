import React, { useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { DemoDataProvider, useDemoData } from '@/context/DemoDataContext';
import { colors, radii, shadows } from '@/theme/theme';
import { PaytmHeader } from '@/components/common/PaytmHeader';
import { BottomNav, NavTab } from '@/components/common/BottomNav';
import { PaytmHomeScreen } from '@/features/home/PaytmHomeScreen';
import HomeScreen from '@/features/home/HomeScreen';
import { KhataScreen } from '@/features/khata/KhataScreen';
import { StockScreen } from '@/features/stock/StockScreen';
import { MoreScreen } from '@/features/more/MoreScreen';
import { SearchModal } from '@/features/home/SearchModal';
import { PaytmPaymentReviewScreen } from '@/features/paymentReview/PaytmPaymentReviewScreen';
import { SupplierScreen } from '@/features/suppliers/SupplierScreen';
import { InvoiceScanScreen } from '@/features/invoices/InvoiceScanScreen';
import { BahiKhataScanScreen } from '@/features/bahiKhata/BahiKhataScanScreen';
import { RemindersScreen } from '@/features/reminders/RemindersScreen';
import { PaytmInsightsScreen } from '@/features/insights/PaytmInsightsScreen';
import { ActivityScreen } from '@/features/activity/ActivityScreen';

type ActiveView =
  | 'home'
  | 'munim_ai'
  | 'khata'
  | 'stock'
  | 'more'
  | 'payment_review'
  | 'suppliers'
  | 'scan_bill'
  | 'bahi_khata'
  | 'reminders'
  | 'insights'
  | 'activity';

function MainAppShell() {
  const { persona, setPersona, pendingReviewCount } = useDemoData();

  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [activeSubView, setActiveSubView] = useState<ActiveView>('home');
  const [searchModalVisible, setSearchModalVisible] = useState(false);

  // Tab change handler
  const handleSelectTab = (tab: NavTab) => {
    setActiveTab(tab);
    if (tab === 'home' || tab === 'khata' || tab === 'stock' || tab === 'more') {
      setActiveSubView(tab);
    }
  };

  // Open Real Munim AI screen (HomeScreen.tsx); the centre mic tab shows as active
  const handleOpenMunimAI = () => {
    setActiveTab('munim');
    setActiveSubView('munim_ai');
  };

  // Sub-view navigators
  const navigateToSubView = (view: ActiveView) => {
    setActiveSubView(view);
  };

  const handleReturnToMain = (tab: 'home' | 'khata' | 'stock' | 'more' = 'home') => {
    setActiveTab(tab);
    setActiveSubView(tab);
  };

  const isMunim = activeSubView === 'munim_ai';

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />

      {isMunim ? (
        <View style={styles.munimNavHeader}>
          <TouchableOpacity
            style={styles.munimBackButton}
            onPress={() => handleReturnToMain('home')}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="Back to Paytm Home"
          >
            <Ionicons name="arrow-back" size={22} color={colors.navy} />
            <Text style={styles.munimBackText}>Back to Paytm Home</Text>
          </TouchableOpacity>
          <View style={styles.munimHeaderTag}>
            <Ionicons name="sparkles" size={14} color={colors.deepCyan} style={{ marginRight: 4 }} />
            <Text style={styles.munimHeaderTagText}>Munim AI Engine</Text>
          </View>
        </View>
      ) : (
        /* Top Paytm Pale-Blue Header */
        <PaytmHeader
          currentPersona={persona}
          onSelectPersona={setPersona}
          onOpenSearch={() => setSearchModalVisible(true)}
        />
      )}

      {/* Main Screen Content Body */}
      <View style={styles.contentBody}>
        {/* Real Munim AI screen (voice, transcription, proposals, confirm) — unchanged logic */}
        {isMunim && <HomeScreen />}

        {activeSubView === 'home' && (
          <PaytmHomeScreen
            onOpenMunim={handleOpenMunimAI}
            onOpenMunimVoice={handleOpenMunimAI}
            onOpenMunimText={handleOpenMunimAI}
            onNavigateTab={(tab) => handleSelectTab(tab)}
            onOpenPaymentReview={() => navigateToSubView('payment_review')}
            onOpenScanBill={() => navigateToSubView('scan_bill')}
            onOpenAddUdhaar={() => {
              setActiveTab('khata');
              setActiveSubView('khata');
            }}
            onOpenRecordJama={() => {
              setActiveTab('khata');
              setActiveSubView('khata');
            }}
            onOpenInsightsBrief={() => navigateToSubView('insights')}
            onOpenActivity={() => navigateToSubView('activity')}
            onOpenSearch={() => setSearchModalVisible(true)}
          />
        )}

        {activeSubView === 'khata' && (
          <KhataScreen
            onOpenReminders={() => navigateToSubView('reminders')}
          />
        )}

        {activeSubView === 'stock' && (
          <StockScreen
            onOpenScanBill={() => navigateToSubView('scan_bill')}
          />
        )}

        {activeSubView === 'more' && (
          <MoreScreen
            onNavigateTo={(screen) => navigateToSubView(screen)}
          />
        )}

        {/* Sub-screens */}
        {activeSubView === 'payment_review' && (
          <PaytmPaymentReviewScreen onBack={() => handleReturnToMain('home')} />
        )}

        {activeSubView === 'suppliers' && (
          <SupplierScreen
            onBack={() => handleReturnToMain('more')}
            onOpenScanBill={() => navigateToSubView('scan_bill')}
          />
        )}

        {activeSubView === 'scan_bill' && (
          <InvoiceScanScreen
            onBack={() => handleReturnToMain('home')}
            onDone={() => handleReturnToMain('stock')}
          />
        )}

        {activeSubView === 'bahi_khata' && (
          <BahiKhataScanScreen
            onBack={() => handleReturnToMain('more')}
            onDone={() => handleReturnToMain('khata')}
          />
        )}

        {activeSubView === 'reminders' && (
          <RemindersScreen onBack={() => handleReturnToMain('more')} />
        )}

        {activeSubView === 'insights' && (
          <PaytmInsightsScreen onBack={() => handleReturnToMain('home')} />
        )}

        {activeSubView === 'activity' && (
          <ActivityScreen onBack={() => handleReturnToMain('home')} />
        )}
      </View>

      {/* Persistent Bottom Navigation */}
      <BottomNav
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        onPressMunim={handleOpenMunimAI}
        reviewCount={pendingReviewCount}
      />

      {/* Search Modal */}
      <SearchModal
        visible={searchModalVisible}
        onClose={() => setSearchModalVisible(false)}
        onSelectCustomer={() => {
          setActiveTab('khata');
          setActiveSubView('khata');
        }}
        onSelectProduct={() => {
          setActiveTab('stock');
          setActiveSubView('stock');
        }}
      />
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <DemoDataProvider>
      <View style={styles.outerFrame}>
        <MainAppShell />
      </View>
    </DemoDataProvider>
  );
}

const styles = StyleSheet.create({
  outerFrame: {
    flex: 1,
    backgroundColor: Platform.OS === 'web' ? '#0B132B' : colors.headerPaleBlue,
    alignItems: 'center',
    justifyContent: 'center',
    ...(Platform.OS === 'web' ? { minHeight: '100vh' } : {}),
  },
  safeArea: {
    flex: 1,
    width: '100%',
    maxWidth: 430, // Restrains to authentic mobile screen width on desktop browsers
    backgroundColor: colors.headerPaleBlue,
    paddingTop: Platform.OS === 'android' ? 24 : 0,
    ...(Platform.OS === 'web'
      ? {
          height: '100vh',
          maxHeight: 920,
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1)',
          overflow: 'hidden',
          borderRadius: 24,
          marginVertical: 16,
        }
      : {}),
  },
  contentBody: {
    flex: 1,
    backgroundColor: colors.background,
  },
  munimNavHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.headerPaleBlue,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  munimBackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingRight: 12,
  },
  munimBackText: {
    marginLeft: 6,
    fontSize: 16,
    fontWeight: '700',
    color: colors.navy,
  },
  munimHeaderTag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  munimHeaderTagText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.navy,
  },
});
