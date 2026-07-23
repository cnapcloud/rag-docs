import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';
import {
  OverviewIcon,
  InstallIcon,
  OperationsIcon,
  ReferenceIcon,
  SupportIcon,
  DemoIcon,
} from './icons';

const FeatureList = [
  {
    title: '개요',
    Icon: OverviewIcon,
    description: '제품 정의, 기능 카탈로그, 아키텍처.',
    to: '/overview/introduction',
  },
  {
    title: '설치',
    Icon: InstallIcon,
    description: '요구사항, Quick Start, k8s 설치, Enterprise 설정, 설치 검증.',
    to: '/deploy/requirements',
  },
  {
    title: '운영',
    Icon: OperationsIcon,
    description: '백업/복구/업그레이드 runbook과 관측 구성.',
    to: '/deploy/runbook',
  },
  {
    title: '레퍼런스',
    Icon: ReferenceIcon,
    description: 'API 가이드, 설정(settings.yaml), 환경변수(.env) 레퍼런스.',
    to: '/reference/api-guide',
  },
  {
    title: '지원',
    Icon: SupportIcon,
    description: '지원 정책, 릴리스/호환성, 알려진 제약.',
    to: '/support/support-policy',
  },
  {
    title: '데모',
    Icon: DemoIcon,
    description: '데모 시나리오.',
    to: '/demo/01-scenario',
  },
];

function Feature({title, Icon, description, to}) {
  return (
    <div className={styles.col}>
      <Link to={to} className={styles.feature}>
        <div className={styles.iconBadge}>
          <Icon />
        </div>
        <Heading as="h3" className={styles.featureTitle}>
          {title}
        </Heading>
        <p className={styles.featureDescription}>{description}</p>
      </Link>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>
          문서 구성
        </Heading>
        <div className={styles.grid}>
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
